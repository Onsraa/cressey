#!/usr/bin/env bash
# Backend on :8000 and Vite on :5173 (which forwards /api); Ctrl-C stops both.
set -euo pipefail
trap 'kill 0' EXIT
cd "$(dirname "$0")"
(cd backend && uv run uvicorn cressey.app:create_app --factory --reload --port 8000) &
(cd web && bun run dev) &
wait
