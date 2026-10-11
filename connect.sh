#!/usr/bin/env bash
# Connect an agent to Cressey (Claude Code for now): create a run, write the hook settings into
# the folder's .claude/settings.local.json, and start claude there. Cressey must be up (./dev.sh).
#
#   ./connect.sh                  # a new scratch folder
#   ./connect.sh ~/my-project     # your own project
#   CRESSEY_TASK="Fix the failing test" ./connect.sh   # the task Cressey judges against
#
# Disconnect: delete <folder>/.claude/settings.local.json. Runs live in memory: after a backend
# restart the old key is refused and so is every tool call, until you run this again.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="${CRESSEY_URL:-http://localhost:8000}"
TASK="${CRESSEY_TASK:-Free chat with Claude Code}"
DIR="${1:-$(mktemp -d)}"
SETTINGS="$DIR/.claude/settings.local.json"

# Never overwrite someone's own local settings: an earlier run of this script left the key line.
if [ -f "$SETTINGS" ] && ! grep -q '/hook/claude' "$SETTINGS"; then
  echo "$SETTINGS exists and is not Cressey's: merge the hooks by hand (Settings > Connect)" >&2
  exit 1
fi

KEY="$(curl -sf "$URL/api/runs" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg task "$TASK" '{task: $task, visibility: "messages"}')" | jq -r .key)" \
  || { echo "no Cressey at $URL: start it with ./dev.sh" >&2; exit 1; }

mkdir -p "$DIR/.claude"
jq 'del(._comment)' "$REPO/lab/cressey-stubs/settings.cressey-hook.example.json" \
  | sed -e "s#CRESSEY_HOOK_URL#$URL#g" -e "s#CRESSEY_RUN_KEY#$KEY#g" > "$SETTINGS"
echo "Cressey is watching $DIR. Dashboard: http://localhost:5173" >&2
cd "$DIR" && exec claude
