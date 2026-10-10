# Shared helpers for the PocketOS replay lab, sourced by status.sh and reset.sh.
# Runs in WSL. Operator auth: the ambient `railway` CLI login (railway api / railway ssh).
# No tokens are read here; reset and status act as the logged-in operator.

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

note() { printf '\033[36m%s\033[0m\n' "$*" >&2; }
ok()   { printf '\033[32m%s\033[0m\n' "$*" >&2; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# Fail early if the operator is not logged in (reset/status are operator-authed).
require_login() {
  "$RAILWAY" whoami >/dev/null 2>&1 || die "not logged in: run 'railway login' first (reset/status act as the operator)."
}

# Run a GraphQL document through the CLI's ambient login. Prints raw JSON.
gql() { "$RAILWAY" api "$1"; }

# Pull a value out of JSON on stdin with a python expression over the parsed object `d`.
jget() { python3 -c 'import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"; }

# The project, with its volume and the environments each volume instance covers.
project_json() {
  gql "query { project(id: \"$LAB_PROJECT_ID\") { name volumes { edges { node { id name volumeInstances { edges { node { environmentId } } } } } } } }"
}

# env name -> env id
env_id() {
  case "$1" in
    staging)    echo "$LAB_ENV_STAGING" ;;
    production) echo "$LAB_ENV_PRODUCTION" ;;
    *) die "unknown environment: $1" ;;
  esac
}

# Reseed one environment's DB with LAB_SEED_ROWS labelled fake rows, over railway ssh.
seed_env() {
  local env="$1"
  local sql="CREATE TABLE IF NOT EXISTS customers (id serial PRIMARY KEY, email text NOT NULL, env text NOT NULL); TRUNCATE customers; INSERT INTO customers (email, env) SELECT 'user' || g || '@${env}.example.test', '${env}' FROM generate_series(1, ${LAB_SEED_ROWS}) g;"
  "$RAILWAY" ssh -s "$LAB_SERVICE_POSTGRES" -e "$(env_id "$env")" -- \
    psql -U postgres -d railway -v ON_ERROR_STOP=1 -q -c "$sql" 2>&1 | grep -v "Using SSH key" || true
}

# Row count + labels in one environment's DB. Empty string if unreachable.
count_env() {
  local env="$1"
  "$RAILWAY" ssh -s "$LAB_SERVICE_POSTGRES" -e "$(env_id "$env")" -- \
    psql -U postgres -d railway -tAc \
    "SELECT coalesce(string_agg(DISTINCT env, ','), '-') || ' x' || count(*) FROM customers;" 2>/dev/null \
    | grep -v "Using SSH key" | tr -d '[:space:]' || true
}

# True if Postgres in one environment answers.
pg_ready() {
  local env="$1"
  "$RAILWAY" ssh -s "$LAB_SERVICE_POSTGRES" -e "$(env_id "$env")" -- \
    pg_isready -U postgres -d railway >/dev/null 2>&1
}
