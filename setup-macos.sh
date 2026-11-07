#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--native" ]; then
    command -v python3.12 >/dev/null 2>&1 || { echo 'Install CPython3.12 first; see README_START_HERE.md.' >&2; exit 1; }
    exec python3.12 -m scripts.lecturer_setup
fi
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 || { echo 'Install/start Docker Desktop; see README_START_HERE.md.' >&2; exit 1; }
docker compose build web db
mkdir -p .local/compose-secrets
chmod 700 .local/compose-secrets
docker compose --profile tools run --rm --no-deps bootstrap
docker compose up -d --wait
echo "Setup OK. Open http://127.0.0.1:${MAHJONG_WEB_PORT:-8000}/ . Next time run ./run-macos.sh."
