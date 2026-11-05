"""Explicit non-destructive tools for a project-owned, socket-only PostgreSQL."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from urllib.parse import urlencode
import uuid

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
ROLE = 'mahjong_phase3'
DATABASES = {'dev': 'mahjong_phase3_dev', 'test': 'mahjong_phase3_test', 'admin': 'postgres'}
MAX_RESTORE_BYTES = 64 * 1024 * 1024


class LocalPostgres:
    def __init__(self, root=ROOT / '.local/phase3-postgres', port=55437):
        self.root = Path(root).resolve()
        self.port = port
        self.data = self.root / 'data'
        self.socket = self.root / 'socket'
        self.marker = self.root / 'project-owner.json'

    def _tool(self, name):
        path = shutil.which(name)
        if not path:
            raise RuntimeError(f'Required PostgreSQL tool is not installed: {name}')
        return path

    def _run(self, args, input_text=None):
        result = subprocess.run(args, capture_output=True, text=True, input=input_text, timeout=40)
        if result.returncode:
            raise RuntimeError(f'PostgreSQL {Path(args[0]).name} failed; inspect this project cluster log')
        return result.stdout

    def _require_owned(self):
        expected = {'project': 'mahjong-phase3', 'root': str(self.root), 'port': self.port, 'role': ROLE}
        if not self.marker.is_file() or json.loads(self.marker.read_text()) != expected:
            raise ValueError('Refusing operation on a PostgreSQL directory not owned by this project tool')

    def initialize(self):
        if self.root.exists() and any(self.root.iterdir()):
            if not self.marker.is_file():
                raise ValueError('Refusing to initialize an unrelated directory')
            self._require_owned()
        else:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.marker.write_text(json.dumps({'project': 'mahjong-phase3', 'root': str(self.root),
                                              'port': self.port, 'role': ROLE})+'\n')
        if not (self.data / 'PG_VERSION').is_file():
            if self.data.exists() and any(self.data.iterdir()):
                raise ValueError('Owned initialization is incomplete; choose a new empty local directory')
            self._run([self._tool('initdb'), '-D', str(self.data), '-U', ROLE, '--auth-local=trust',
                       '--auth-host=scram-sha-256', '--locale=C', '--encoding=UTF8'])
        self.socket.mkdir(exist_ok=True, mode=0o700)
        self.socket.chmod(0o700)

    def running(self):
        self._require_owned()
        return subprocess.run([self._tool('pg_ctl'), '-D', str(self.data), 'status'],
                              capture_output=True).returncode == 0

    def start(self):
        self._require_owned()
        if not self.running():
            options = shlex.join(['-h', '', '-k', str(self.socket), '-p', str(self.port),
                                  '-c', 'unix_socket_permissions=0700'])
            self._run([self._tool('pg_ctl'), '-D', str(self.data), '-l', str(self.root/'postgres.log'),
                       '-o', options, '-w', 'start'])
        with self.connect('postgres') as connection:
            for name in (DATABASES['dev'], DATABASES['test']):
                if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone():
                    connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))

    def stop(self):
        self._require_owned()
        if self.running():
            self._run([self._tool('pg_ctl'), '-D', str(self.data), '-m', 'fast', '-w', 'stop'])

    def database_url(self, kind):
        if kind not in DATABASES:
            raise ValueError('Choose only a project dev/test/admin database')
        return self.url_for_database(DATABASES[kind])

    def url_for_database(self, name):
        if name not in DATABASES.values() and not name.startswith('mahjong_phase3_restore_'):
            raise ValueError('Database is outside the project namespace')
        return f'postgresql+psycopg://{ROLE}@/{name}?'+urlencode({'host':str(self.socket),'port':str(self.port)})

    def connect(self, database):
        self._require_owned()
        self.url_for_database(database)
        return psycopg.connect(dbname=database, user=ROLE, host=str(self.socket), port=self.port,
                               connect_timeout=3, autocommit=True)

    def export_sql(self, kind, destination):
        self._require_owned()
        if kind not in ('dev', 'test'):
            raise ValueError('Export only a project dev/test database')
        destination = Path(destination).resolve()
        if destination.exists():
            raise FileExistsError('Choose a new SQL export filename; existing evidence is preserved')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='export-',dir=self.root) as private:
            captured=Path(private)/'prediction_results.sql'
            self._run([self._tool('pg_dump'), '-h', str(self.socket), '-p', str(self.port), '-U', ROLE,
                       '-d', DATABASES[kind], '--no-owner', '--no-privileges', '--table=prediction_results',
                       '--file', str(captured)])
            content=self._read_sql(captured)
            self._check_restore_boundary(content.decode('utf-8'))
            with destination.open('xb') as output:output.write(content)
        digest=hashlib.sha256(content).hexdigest()
        receipts=self.root/'verified-exports';receipts.mkdir(exist_ok=True,mode=0o700)
        receipt=receipts/(digest+'.json')
        if not receipt.exists():
            receipt.write_text(json.dumps({'project':'mahjong-phase3','sha256':digest,'bytes':len(content),
                                          'table':'prediction_results'})+'\n')
        return destination

    @staticmethod
    def _read_sql(source):
        if not source.is_file():
            raise ValueError('A verified project SQL export is required')
        size=source.stat().st_size
        if not 0<size<=MAX_RESTORE_BYTES:
            raise ValueError('SQL input size must be nonempty and at most 64 MiB')
        with source.open('rb') as stream:content=stream.read(MAX_RESTORE_BYTES+1)
        if not 0<len(content)<=MAX_RESTORE_BYTES:
            raise ValueError('SQL input size is empty or too large')
        return content

    @staticmethod
    def _check_restore_boundary(content):
        copying=False
        for line in content.splitlines():
            stripped=line.strip()
            if copying:
                if stripped==r'\.':copying=False
                continue
            if not stripped or stripped.startswith('--'):continue
            if stripped.startswith('COPY '):
                if not re.fullmatch(r'COPY public\.prediction_results \([^)]+\) FROM stdin;',stripped):
                    raise ValueError('Unsafe SQL restore COPY target')
                copying=True;continue
            if '\\' in stripped and not re.fullmatch(r'\\(?:unrestrict|restrict) [A-Za-z0-9]+',stripped):
                raise ValueError('Unsafe SQL restore meta-command')
            if re.search(r'\b(?:CREATE|ALTER|DROP)\s+(?:DATABASE|ROLE|USER|TABLESPACE|SYSTEM)\b',stripped,re.I):
                raise ValueError('Unsafe SQL restore database-level operation')
        if copying:raise ValueError('Unsafe incomplete SQL COPY input')

    def restore_sql(self, source):
        self._require_owned()
        source = Path(source).resolve()
        content=self._read_sql(source)
        digest=hashlib.sha256(content).hexdigest()
        receipt=self.root/'verified-exports'/(digest+'.json')
        try:verification=json.loads(receipt.read_text())
        except (OSError,ValueError):
            raise ValueError('Only a checksum-verified export from this project cluster can be restored') from None
        if verification!={'project':'mahjong-phase3','sha256':digest,'bytes':len(content),'table':'prediction_results'}:
            raise ValueError('The project export is not verified')
        try:sql_input=content.decode('utf-8')
        except UnicodeDecodeError:raise ValueError('Unsafe SQL encoding') from None
        self._check_restore_boundary(sql_input)
        name = 'mahjong_phase3_restore_'+uuid.uuid4().hex[:12]
        with self.connect('postgres') as connection:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        self._run([self._tool('psql'), '-h', str(self.socket), '-p', str(self.port), '-U', ROLE,
                   '-d', name, '--no-psqlrc', '--set=ON_ERROR_STOP=1', '--single-transaction', '--file', '-'],
                  input_text=sql_input)
        return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init','start','stop','status','url','export','restore'))
    parser.add_argument('--root', type=Path, default=ROOT/'.local/phase3-postgres')
    parser.add_argument('--database', choices=('dev','test'), default='dev')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--input', type=Path)
    args = parser.parse_args();controller = LocalPostgres(args.root)
    if args.command == 'init':controller.initialize()
    elif args.command == 'start':controller.initialize();controller.start()
    elif args.command == 'stop':controller.stop()
    elif args.command == 'status':print(json.dumps({'running':controller.running()}))
    elif args.command == 'url':print(controller.database_url(args.database))
    elif args.command == 'export':
        if args.output is None:parser.error('--output is required for export')
        print(controller.export_sql(args.database,args.output))
    elif args.command == 'restore':
        if args.input is None:parser.error('--input is required for restore')
        print(controller.restore_sql(args.input))


if __name__ == '__main__':main()
