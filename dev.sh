#!/usr/bin/env bash
# Backend on :8000 and Vite on :5173 (which forwards /api); Ctrl-C stops both.
set -euo pipefail
trap 'kill 0' EXIT
cd "$(dirname "$0")"
# The control plane's key (CRESSEY_ADMIN_TOKEN): the dashboard asks for it once, and agents
# never hold it. Drawn once into .env, which the backend reads.
[ -f .env ] || cp .env.example .env
if ! grep -qE '^CRESSEY_ADMIN_TOKEN=.+' .env; then
  { grep -v '^CRESSEY_ADMIN_TOKEN=' .env || true
    printf 'CRESSEY_ADMIN_TOKEN=%s\n' "$(od -An -tx1 -N24 /dev/urandom | tr -d ' \n')"; } > .env.tmp
  mv .env.tmp .env
  chmod 600 .env
fi
# The event log and the runs' keys survive a restart, in backend/data/state (git-ignored).
(cd backend && CRESSEY_STATE_DIR=data/state uv run uvicorn cressey.app:create_app --factory --reload --port 8000) &
(cd web && bun run dev) &
wait
