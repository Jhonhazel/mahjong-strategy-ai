import secrets
import uuid

import pytest
from psycopg import sql
from sqlalchemy import Integer, MetaData
from fastapi.testclient import TestClient

from tests.phase3_support import local_postgres_controller, postgres_engine, postgres_url, web_settings
from tests.test_phase3_history import sample_snapshot

pytestmark=pytest.mark.integration


def new_database(controller):
    name='mahjong_phase3_restore_'+uuid.uuid4().hex[:12]
    with controller.connect('postgres') as connection:
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    return name


def test_real_postgres_sql_export_restore_preserves_schema_and_records(local_postgres_controller,postgres_engine,tmp_path,web_settings):
    from app.db import create_db_engine,check_schema
    from app.services.prediction_history_service import PredictionHistoryService
    controller=local_postgres_controller;owner=secrets.token_hex(32);store=PredictionHistoryService(postgres_engine)
    record,_=store.save(owner,sample_snapshot())
    export=controller.export_sql('test',tmp_path/'history.sql')
    assert export.is_file() and 'CREATE TABLE public.prediction_results' in export.read_text()
    with pytest.raises(FileExistsError):controller.export_sql('test',export)
    restored_name=controller.restore_sql(export)
    engine=create_db_engine(web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(restored_name))}))
    try:
        assert check_schema(engine)['status']=='PASS'
        restored=PredictionHistoryService(engine).get(owner,record.id)
        assert restored.input_snapshot==record.input_snapshot and restored.output_snapshot==record.output_snapshot
        assert restored.created_at==record.created_at and restored.model_version==record.model_version
    finally:engine.dispose()


def test_missing_schema_blocks_startup_and_partial_resources_are_closed(local_postgres_controller,web_settings):
    from app.db import DatabaseUnavailable
    from app.main import create_app
    controller=local_postgres_controller;name=new_database(controller)
    config=web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(name))})
    app=create_app(config)
    with pytest.raises(DatabaseUnavailable,match='schema is missing'):
        with TestClient(app):pass
    assert app.state.resources is None and app.state.initializing is False


def test_incompatible_postgres_column_type_is_rejected_before_readiness(local_postgres_controller,web_settings):
    from app.db import PredictionResult,DatabaseUnavailable,check_schema,create_db_engine
    controller=local_postgres_controller;name=new_database(controller)
    config=web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(name))})
    engine=create_db_engine(config)
    try:
        clone=PredictionResult.__table__.to_metadata(MetaData());clone.c.owner_key.type=Integer()
        clone.create(engine)
        with pytest.raises(DatabaseUnavailable,match='incompatible'):check_schema(engine)
    finally:engine.dispose()


@pytest.mark.parametrize('drift',[
    "ALTER TABLE prediction_results ALTER COLUMN created_at SET DEFAULT '2000-01-01T00:00:00Z'::timestamptz",
    'ALTER TABLE prediction_results DROP CONSTRAINT ck_prediction_turn; ALTER TABLE prediction_results ADD CONSTRAINT ck_prediction_turn CHECK (true)',
    'ALTER TABLE prediction_results DROP CONSTRAINT ck_prediction_phase; ALTER TABLE prediction_results ADD CONSTRAINT ck_prediction_phase CHECK (true)',
    'ALTER TABLE prediction_results DROP CONSTRAINT ck_prediction_digests; ALTER TABLE prediction_results ADD CONSTRAINT ck_prediction_digests CHECK (true)',
    'ALTER TABLE prediction_results DROP CONSTRAINT uq_prediction_snapshot; ALTER TABLE prediction_results ADD CONSTRAINT uq_prediction_snapshot UNIQUE(owner_key,game_id,turn_number,model_version,state_digest) DEFERRABLE INITIALLY DEFERRED',
    'ALTER TABLE prediction_results ADD COLUMN source TEXT NOT NULL',
])
def test_semantically_drifted_schema_is_not_ready(local_postgres_controller,web_settings,drift):
    from sqlalchemy import text
    from app.db import initialize_schema,check_schema,create_db_engine,DatabaseUnavailable
    controller=local_postgres_controller;name=new_database(controller)
    config=web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(name))})
    engine=create_db_engine(config)
    try:
        initialize_schema(engine)
        with engine.begin() as connection:
            for statement in drift.split(';'):connection.execute(text(statement))
        with pytest.raises(DatabaseUnavailable):check_schema(engine)
    finally:engine.dispose()


@pytest.mark.parametrize('content',[
    '\\connect mahjong_phase3_dev\nSELECT 1;',
    'CREATE DATABASE outside_project;',
    'DROP DATABASE mahjong_phase3_dev;',
    'ALTER DATABASE mahjong_phase3_dev RENAME TO outside_project;',
])
def test_restore_rejects_unverified_or_connection_changing_input_before_execution(local_postgres_controller,tmp_path,monkeypatch,content):
    controller=local_postgres_controller;source=tmp_path/'untrusted.sql';source.write_text(content)
    def unexpected(*args,**kwargs):pytest.fail('Unverified SQL reached database/process execution')
    monkeypatch.setattr(controller,'connect',unexpected);monkeypatch.setattr(controller,'_run',unexpected)
    with pytest.raises(ValueError,match='verified|unsafe'):controller.restore_sql(source)


def test_restore_rejects_tampered_project_export(local_postgres_controller,postgres_engine,tmp_path,monkeypatch):
    controller=local_postgres_controller;source=controller.export_sql('test',tmp_path/'tampered.sql')
    source.write_text(source.read_text()+'\n\\connect mahjong_phase3_dev\n')
    def unexpected(*args,**kwargs):pytest.fail('Tampered SQL reached execution')
    monkeypatch.setattr(controller,'connect',unexpected);monkeypatch.setattr(controller,'_run',unexpected)
    with pytest.raises(ValueError,match='verified|unsafe'):controller.restore_sql(source)


@pytest.mark.parametrize('size',[0,2049])
def test_restore_input_size_is_bounded_before_read_or_database_execution(local_postgres_controller,tmp_path,monkeypatch,size):
    from scripts import phase3_db
    controller=local_postgres_controller;source=tmp_path/'bounded.sql'
    with source.open('wb') as output:output.truncate(size)
    monkeypatch.setattr(phase3_db,'MAX_RESTORE_BYTES',2048,raising=False)
    def unexpected(*args,**kwargs):pytest.fail('Invalid-sized SQL reached execution')
    monkeypatch.setattr(controller,'connect',unexpected);monkeypatch.setattr(controller,'_run',unexpected)
    with pytest.raises(ValueError,match='size|empty|large'):controller.restore_sql(source)


@pytest.mark.parametrize('replacement',['KEEP existing file',r'SELECT 1 \connect mahjong_phase3_dev'])
def test_export_attests_private_bytes_and_never_clobbers_a_racing_destination(local_postgres_controller,postgres_engine,tmp_path,monkeypatch,replacement):
    import hashlib
    controller=local_postgres_controller;destination=tmp_path/'shared.sql';run=controller._run
    def racing_writer(args,input_text=None):
        result=run(args,input_text)
        if '--file' in args:destination.write_text(replacement)
        return result
    monkeypatch.setattr(controller,'_run',racing_writer)
    with pytest.raises(FileExistsError):controller.export_sql('test',destination)
    assert destination.read_text()==replacement
    digest=hashlib.sha256(replacement.encode()).hexdigest()
    assert not (controller.root/'verified-exports'/(digest+'.json')).exists()


@pytest.mark.parametrize('command',[r'SELECT 1 \connect mahjong_phase3_dev',r'SELECT 1 \gexec',r'SELECT 1 \! whoami'])
def test_restore_boundary_rejects_midline_psql_commands(command):
    from scripts.phase3_db import LocalPostgres
    with pytest.raises(ValueError,match='unsafe|Unsafe'):LocalPostgres._check_restore_boundary(command)


def test_read_only_postgres_connection_is_not_ready(local_postgres_controller,web_settings):
    from sqlalchemy import text
    from app.db import initialize_schema,check_schema,create_db_engine,DatabaseUnavailable
    controller=local_postgres_controller;name=new_database(controller)
    config=web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(name))})
    engine=create_db_engine(config)
    try:
        initialize_schema(engine)
        with engine.connect() as connection:
            connection.execute(text('SET default_transaction_read_only=on'));connection.commit()
        with pytest.raises(DatabaseUnavailable):check_schema(engine)
    finally:engine.dispose()


def test_postgres_role_requires_real_insert_delete_and_row_lock_privileges(local_postgres_controller,web_settings):
    from sqlalchemy.engine import make_url
    from app.db import initialize_schema,check_schema,create_db_engine,DatabaseUnavailable
    controller=local_postgres_controller;name=new_database(controller);role='mahjong_phase3_probe_'+uuid.uuid4().hex[:12]
    config=web_settings.model_copy(update={'database_url':type(web_settings.database_url)(controller.url_for_database(name))})
    engine=create_db_engine(config)
    try:initialize_schema(engine)
    finally:engine.dispose()
    with controller.connect(name) as connection:
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
        connection.execute(sql.SQL('GRANT SELECT ON prediction_results TO {}').format(sql.Identifier(role)))
    limited=make_url(controller.url_for_database(name)).set(username=role).render_as_string(hide_password=False)
    engine=create_db_engine(config.model_copy(update={'database_url':type(config.database_url)(limited)}))
    try:
        with pytest.raises(DatabaseUnavailable):check_schema(engine)
    finally:engine.dispose()
