#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--native" ]; then
    [ -x .venv/bin/python ] || { echo 'Run ./setup-macos.sh --native first.' >&2; exit 1; }
    exec .venv/bin/python -m scripts.lecturer_setup --run
fi
exec docker compose up
