#!/usr/bin/env bash
# Restore the PocketOS replay lab to a known baseline after a test run.
# Production holds the seeded data; staging's Postgres is config-only (not seeded).
# Idempotent: safe to run whether a run only altered rows or deleted the whole volume.
#
#   wsl -e bash lab/reset.sh
#
# Operator-authed: uses the ambient `railway` CLI login. Run while logged in,
# then `railway logout` before an agent run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_login

PROD_ENV="$LAB_ENV_PRODUCTION"

# --- 1. Volume: recreate it if a run deleted it -----------------------------
pj="$(project_json)"
vol_present="$(printf '%s' "$pj" | python3 -c '
import sys, json
d = json.load(sys.stdin)
vid = sys.argv[1]
print("yes" if any(e["node"]["id"] == vid for e in d["data"]["project"]["volumes"]["edges"]) else "no")
' "$LAB_VOLUME_ID")"

if [ "$vol_present" = "no" ]; then
  warn "volume gone — recreating and redeploying production Postgres"
  # environmentId omitted => attach to all environments, mirroring the original.
  created="$(gql "mutation { volumeCreate(input: { projectId: \"$LAB_PROJECT_ID\", serviceId: \"$LAB_SERVICE_POSTGRES\", mountPath: \"$LAB_VOLUME_MOUNT\" }) { id } }" 2>&1 || true)"
  if ! printf '%s' "$created" | grep -q '"id"'; then
    warn "all-env volumeCreate failed, retrying production-only"
    warn "$created"
    created="$(gql "mutation { volumeCreate(input: { projectId: \"$LAB_PROJECT_ID\", serviceId: \"$LAB_SERVICE_POSTGRES\", mountPath: \"$LAB_VOLUME_MOUNT\", environmentId: \"$PROD_ENV\" }) { id } }")"
  fi
  new_id="$(printf '%s' "$created" | jget 'd["data"]["volumeCreate"]["id"]')"
  ok "created volume $new_id"
  note "if this id differs from lab.env LAB_VOLUME_ID, update lab.env"
  gql "mutation { serviceInstanceRedeploy(serviceId: \"$LAB_SERVICE_POSTGRES\", environmentId: \"$PROD_ENV\") }" >/dev/null
  ok "redeploy triggered for production Postgres"
else
  note "volume present"
fi

# --- 2. Wait for production Postgres to answer ------------------------------
note "waiting for production Postgres…"
ready=no
for i in $(seq 1 60); do
  if pg_ready production; then ready=yes; break; fi
  sleep 5
done
[ "$ready" = yes ] || die "production Postgres did not become ready in time"
ok "production Postgres ready"

# --- 3. Reseed production ---------------------------------------------------
note "reseeding production ($LAB_SEED_ROWS labelled rows)…"
seed_env production

# --- 4. Confirm -------------------------------------------------------------
note "final state:"
bash "$LAB_DIR/status.sh"
ok "reset complete"
