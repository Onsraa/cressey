#!/usr/bin/env bash
# Restore the PocketOS replay lab to a known baseline after a test run.
# Production holds the seeded data; staging's Postgres is config-only (not seeded).
# Idempotent: if a run deleted the Postgres service (or its volume), rebuild it via
# provision.sh; otherwise just reseed production.
#
#   wsl -e bash lab/reset.sh
#
# Operator-authed: uses the ambient `railway` CLI login. Run while logged in,
# then `railway logout` before an agent run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_login

if ! pg_service_exists; then
  warn "production Postgres service is gone — rebuilding via provision.sh"
  exec bash "$LAB_DIR/provision.sh"
fi

# Service is up: make sure it answers, then reseed.
note "waiting for production Postgres…"
ready=no
for _ in $(seq 1 60); do
  pg_forget
  if pg_ready production; then ready=yes; break; fi
  sleep 5
done
[ "$ready" = yes ] || die "production Postgres did not answer; try: wsl -e bash lab/provision.sh"
ok "production Postgres ready"

note "tidying up any extra services/volumes a run created…"
clean_extras run

note "reseeding production ($LAB_SEED_ROWS labelled rows)…"
seed_env production

note "final state:"
bash "$LAB_DIR/status.sh"
ok "reset complete"
