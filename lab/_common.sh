# Shared helpers for the PocketOS replay lab, sourced by status.sh, reset.sh, provision.sh.
# Runs in WSL. Operator auth: the ambient `railway` CLI login (railway api / railway ssh).
# No tokens are read here; the lab scripts act as the logged-in operator.
#
# The Postgres service and its volume are recreated by provision.sh, so their ids change.
# Everything here resolves the production Postgres service id at runtime, by name, rather
# than trusting a constant. Only the project and environment ids are stable (lab.env).

set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$LAB_DIR")"

# shellcheck disable=SC1091
source "$LAB_DIR/lab.env"

RAILWAY="${RAILWAY_BIN:-$HOME/.railway/bin/railway}"
[ -x "$RAILWAY" ] || RAILWAY="$(command -v railway || true)"
if [ -z "$RAILWAY" ] || [ ! -x "$RAILWAY" ]; then
  echo "error: railway CLI not found (set RAILWAY_BIN)" >&2
  exit 1
fi
PG_SERVICE_NAME="${LAB_PG_SERVICE_NAME:-Postgres}"

note() { printf '\033[36m%s\033[0m\n' "$*" >&2; }
ok()   { printf '\033[32m%s\033[0m\n' "$*" >&2; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# Fail early if the operator is not logged in (the lab scripts are operator-authed).
require_login() {
  "$RAILWAY" whoami >/dev/null 2>&1 || die "not logged in: run 'railway login' first."
}

# Run a GraphQL document through the CLI's ambient login. Prints raw JSON.
gql() { "$RAILWAY" api "$1"; }

# env name -> env id (stable, from lab.env)
env_id() {
  case "$1" in
    staging)    echo "$LAB_ENV_STAGING" ;;
    production) echo "$LAB_ENV_PRODUCTION" ;;
    *) die "unknown environment: $1" ;;
  esac
}

# The project's services and volumes, with the environments/services each instance covers.
project_json() {
  gql "query { project(id: \"$LAB_PROJECT_ID\") { name services { edges { node { id name serviceInstances { edges { node { environmentId latestDeployment { status } } } } } } } volumes { edges { node { id name volumeInstances { edges { node { environmentId serviceId } } } } } } } }"
}

# The id of the production Postgres service, resolved by name. Empty if it doesn't exist.
# Cached for the life of the process.
_PG_SVC=""
pg_service_id() {
  if [ -z "$_PG_SVC" ]; then
    _PG_SVC="$(project_json | PG_NAME="$PG_SERVICE_NAME" PROD="$LAB_ENV_PRODUCTION" python3 -c '
import sys, json, os
d = json.load(sys.stdin)
name, prod = os.environ["PG_NAME"], os.environ["PROD"]
for e in d["data"]["project"]["services"]["edges"]:
    n = e["node"]
    if n["name"] == name and any(i["node"]["environmentId"] == prod for i in n["serviceInstances"]["edges"]):
        print(n["id"]); break
' 2>/dev/null || true)"
  fi
  printf '%s' "$_PG_SVC"
}

# True if the production Postgres service exists.
pg_service_exists() { [ -n "$(pg_service_id)" ]; }

# Reseed one environment's DB with LAB_SEED_ROWS labelled fake rows, over railway ssh.
seed_env() {
  local env="$1" svc; svc="$(pg_service_id)"
  [ -n "$svc" ] || die "no Postgres service to seed (run provision.sh)"
  local sql="CREATE TABLE IF NOT EXISTS customers (id serial PRIMARY KEY, email text NOT NULL, env text NOT NULL); TRUNCATE customers; INSERT INTO customers (email, env) SELECT 'user' || g || '@${env}.example.test', '${env}' FROM generate_series(1, ${LAB_SEED_ROWS}) g;"
  "$RAILWAY" ssh -s "$svc" -e "$(env_id "$env")" -- \
    psql -U postgres -d railway -v ON_ERROR_STOP=1 -q -c "$sql" 2>&1 | grep -v "Using SSH key" || true
}

# Row count + labels in one environment's DB. Empty string if unreachable or no service.
count_env() {
  local env="$1" svc; svc="$(pg_service_id)"
  [ -n "$svc" ] || { echo ""; return; }
  "$RAILWAY" ssh -s "$svc" -e "$(env_id "$env")" -- \
    psql -U postgres -d railway -tAc \
    "SELECT coalesce(string_agg(DISTINCT env, ','), '-') || ' x' || count(*) FROM customers;" 2>/dev/null \
    | grep -v "Using SSH key" | tr -d '[:space:]' || true
}

# True if Postgres in one environment really answers a query. Uses a real SELECT, not
# pg_isready: when a service has no live deployment, `railway ssh` falls back to Railway's
# SSH assistant, which returns 0 and a JSON blob — a false "ready". We require the exact
# query output instead.
pg_ready() {
  local env="$1" svc out; svc="$(pg_service_id)"
  [ -n "$svc" ] || return 1
  out="$("$RAILWAY" ssh -s "$svc" -e "$(env_id "$env")" -- \
    psql -U postgres -d railway -tAc "SELECT 42;" 2>/dev/null | tr -d '[:space:]')"
  [ "$out" = "42" ]
}

# Forget the cached service id (after provision creates a new one).
pg_forget() { _PG_SVC=""; }

# List the extras to tidy: every service except the canonical prod Postgres, and every
# volume not attached to it. One per line: "svc <id> <name>" or "vol <id> <name>".
# Prints nothing (and returns 1) if the canonical Postgres can't be resolved, so a bad
# query can never cascade into deleting the keeper.
extras() {
  local keep; keep="$(pg_service_id)"
  [ -n "$keep" ] || { warn "no canonical Postgres resolved — refusing to compute extras"; return 1; }
  project_json | KEEP="$keep" python3 -c '
import sys, json, os
d = json.load(sys.stdin)["data"]["project"]
keep = os.environ["KEEP"]
for e in d["services"]["edges"]:
    n = e["node"]
    if n["id"] != keep:
        print("svc", n["id"], n["name"])
for v in d["volumes"]["edges"]:
    n = v["node"]
    attached_to_keeper = any(i["node"].get("serviceId") == keep for i in n["volumeInstances"]["edges"])
    if not attached_to_keeper:
        print("vol", n["id"], n["name"])
'
}

# Delete those extras. Pass "dry" to only print what would go.
clean_extras() {
  local mode="${1:-run}" line kind id name
  extras | while read -r kind id name; do
    if [ "$mode" = dry ]; then
      echo "would delete $kind $name (${id:0:8}…)" >&2
      continue
    fi
    note "deleting $kind $name (${id:0:8}…)"
    if [ "$kind" = svc ]; then
      gql "mutation { serviceDelete(id: \"$id\") }" >/dev/null 2>&1 || warn "  serviceDelete failed for $name"
    else
      gql "mutation { volumeDelete(volumeId: \"$id\") }" >/dev/null 2>&1 || warn "  volumeDelete failed for $name (may be attached/soft-deleting)"
    fi
  done
}
