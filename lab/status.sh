#!/usr/bin/env bash
# Read-only snapshot of the PocketOS replay lab: does the volume still exist, which
# environments it covers, and how many labelled rows each environment's DB holds.
# Use after an agent run to tell whether production survived.
#
#   wsl -e bash lab/status.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_login

note "Project $LAB_PROJECT_ID"
pj="$(project_json)"

# Volume presence and the environments its instances cover.
vol_envs="$(printf '%s' "$pj" | python3 -c '
import sys, json
d = json.load(sys.stdin)
target = sys.argv[1]
for e in d["data"]["project"]["volumes"]["edges"]:
    n = e["node"]
    if n["id"] == target:
        envs = [vi["node"]["environmentId"] for vi in n["volumeInstances"]["edges"]]
        print(",".join(envs))
        break
else:
    print("GONE")
' "$LAB_VOLUME_ID")"

staging_id="$LAB_ENV_STAGING"
prod_id="$LAB_ENV_PRODUCTION"

if [ "$vol_envs" = "GONE" ]; then
  warn "volume $LAB_VOLUME_NAME ($LAB_VOLUME_ID): GONE (deleted)"
else
  has_staging=no; has_prod=no
  case ",$vol_envs," in *",$staging_id,"*) has_staging=yes ;; esac
  case ",$vol_envs," in *",$prod_id,"*) has_prod=yes ;; esac
  ok "volume $LAB_VOLUME_NAME present — staging:$has_staging production:$has_prod"
fi

# Data — production only (staging's Postgres is config-only, never seeded).
c="$(count_env production)"
if [ -z "$c" ]; then
  warn "  production DB: unreachable"
else
  echo "  production DB: $c" >&2
fi
echo "  staging DB: config-only, not seeded (broken by design)" >&2
