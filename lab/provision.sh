#!/usr/bin/env bash
# (Re)build the production Postgres service of the PocketOS lab from the Railway template,
# then seed it. Idempotent: if the service is already up it just reseeds. Used to recover
# after a run deletes the service (or the volume), so the demo is repeatable.
#
#   wsl -e bash lab/provision.sh
#
# Operator-authed (ambient railway CLI login). The CLI must be linked to the lab project;
# this re-links a working dir to be safe.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_login

WORKDIR="${LAB_WORKDIR:-$HOME/cressey-lab}"
mkdir -p "$WORKDIR"

if pg_service_exists; then
  note "production Postgres already present — reseeding only"
else
  note "production Postgres is gone — provisioning from the Railway template"
  ( cd "$WORKDIR"
    "$RAILWAY" link -p "$LAB_PROJECT_ID" -e production >/dev/null 2>&1 || true
    "$RAILWAY" environment production >/dev/null 2>&1 || true
    "$RAILWAY" add -d postgres -s "$PG_SERVICE_NAME" </dev/null ) 2>&1 | grep -vi "using ssh key" || true
  ok "add requested; waiting for the service to come up"
  pg_forget
fi

# Wait for production Postgres to answer (build + deploy can take a few minutes).
note "waiting for production Postgres…"
ready=no
for _ in $(seq 1 90); do
  pg_forget
  if pg_ready production; then ready=yes; break; fi
  sleep 5
done
[ "$ready" = yes ] || die "production Postgres did not become ready in time (check the Railway dashboard)"
ok "production Postgres ready"

note "tidying up any extra services/volumes…"
clean_extras run

note "seeding production ($LAB_SEED_ROWS labelled rows)…"
seed_env production

note "final state:"
bash "$LAB_DIR/status.sh"
ok "provision complete"
