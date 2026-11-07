"""PyInstaller entry; child modes use the same authentic factory/schema code."""
import argparse
from pathlib import Path
import signal
import sys

from scripts.windows_launcher import LauncherError,run_offline


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');parser.add_argument('--init-schema',action='store_true');parser.add_argument('--stop',action='store_true')
    args=parser.parse_args()
    if not getattr(sys,'frozen',False):raise LauncherError('This entry must be built on Windows first; use existing source startup for development')
    if args.serve:
        # CTRL_BREAK is sent only to the child process group owned by the launcher.
        if hasattr(signal,'SIGBREAK'):signal.signal(signal.SIGBREAK,lambda *_:signal.raise_signal(signal.SIGINT))
        from scripts.run_backend import main as serve
        serve();return 0
    if args.init_schema:
        from scripts.init_db import main as init
        init();return 0
    return run_offline(Path(sys.executable).resolve().parent.parent,Path(sys._MEIPASS),stop=args.stop)


if __name__=='__main__':
    try:raise SystemExit(main())
    except LauncherError as error:print('Mahjong startup failed: '+str(error),file=sys.stderr);raise SystemExit(1)
