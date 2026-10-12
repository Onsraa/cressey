#!/usr/bin/env bash
# Try Cressey on your own agent in one command (Claude Code for now). On a first run it asks for
# your Jev API key, installs what's missing and starts Cressey. Then it opens the dashboard and
# Claude Code, watched by Cressey, in a new scratch folder or the folder you give.
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
DASHBOARD="http://localhost:5173"
TASK="${CRESSEY_TASK:-Free chat with Claude Code}"
DIR="${1:-$(mktemp -d)}"
SETTINGS="$DIR/.claude/settings.local.json"
ENV="$REPO/.env"
LOG="${TMPDIR:-/tmp}/cressey-dev.log"

for tool in uv bun jq curl claude; do
  command -v "$tool" >/dev/null || { echo "missing: $tool (see the README's Install)" >&2; exit 1; }
done

# Never overwrite someone's own local settings: an earlier run of this script left the hook URL.
if [ -f "$SETTINGS" ] && ! grep -q '/hook/claude' "$SETTINGS"; then
  echo "$SETTINGS exists and is not Cressey's: merge the hooks by hand (Settings > Connect)" >&2
  exit 1
fi

# One tiny Jev call: exit 0 when the key works, 1 when Jev refuses it, 2 when Jev can't be reached.
CHECK='import os, sys, typesafe_sdk as t
try:
    t.TypeSafeClient(api_key=os.environ["JEV_KEY"], timeout=10).system_one(
        state={"text": "hello"}, questions={"q": t.Noul(instructions="The text is a greeting.")})
except (t.TypeSafeAuthenticationError, t.TypeSafePermissionDeniedError):
    sys.exit(1)
except Exception:
    sys.exit(2)'

ask_key() {
  local key code
  echo "Cressey reads what your agent says and does with Jev, TypeSafe's decision model." >&2
  while :; do
    printf 'Paste your Jev API key (TYPESAFE_API_KEY), then press Enter: ' >&2
    IFS= read -rs key || { echo "no key given" >&2; exit 1; }
    echo >&2
    [ -n "$key" ] || continue
    code=0
    JEV_KEY="$key" uv run -q --project "$REPO/backend" python -I -c "$CHECK" || code=$?
    case "$code" in
      0) echo "Key accepted." >&2; break ;;
      1) echo "Jev refused this key. Try again." >&2 ;;
      *) echo "Couldn't reach Jev to check the key. Saving it anyway." >&2; break ;;
    esac
  done
  { grep -v '^TYPESAFE_API_KEY=' "$ENV" || true; printf 'TYPESAFE_API_KEY=%s\n' "$key"; } > "$ENV.tmp"
  mv "$ENV.tmp" "$ENV"
  chmod 600 "$ENV"
}

up() { curl -sf "$URL/api/health" >/dev/null && curl -sf "$DASHBOARD" >/dev/null; }

# Cressey started here stops when you're done, once you've had a last look at the dashboard.
started=""
stop() {
  if up; then
    printf '\nThe dashboard stays up at %s. Press Enter to stop Cressey. ' "$DASHBOARD" >&2
    read -r _ || true
  fi
  kill -- -"$started" 2>/dev/null || true
}

if ! up; then
  [ -f "$ENV" ] || cp "$REPO/.env.example" "$ENV"
  grep -qE '^TYPESAFE_API_KEY=.+' "$ENV" || ask_key
  [ -d "$REPO/web/node_modules" ] || (cd "$REPO/web" && bun install)
  echo "Starting Cressey (the first start installs its packages, log: $LOG)..." >&2
  set -m  # dev.sh gets its own process group, so stopping it never touches this script
  "$REPO/dev.sh" < /dev/null > "$LOG" 2>&1 &
  started=$!
  set +m
  trap stop EXIT
  for _ in $(seq 1 300); do up && break; sleep 1; done
  up || { echo "Cressey did not start: see $LOG" >&2; exit 1; }
fi

# The control plane's key, which ./dev.sh draws into .env. Not exported: the agent started
# below never inherits it.
CRESSEY_ADMIN="$({ grep '^CRESSEY_ADMIN_TOKEN=' "$ENV" || true; } | cut -d= -f2- | tr -d '\r')"
[ -n "$CRESSEY_ADMIN" ] || { echo "CRESSEY_ADMIN_TOKEN is missing in $ENV: start Cressey with ./dev.sh" >&2; exit 1; }
KEY="$(curl -sf "$URL/api/runs" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $CRESSEY_ADMIN" \
  -d "$(jq -n --arg task "$TASK" '{task: $task, visibility: "messages"}')" | jq -r .key)"
mkdir -p "$DIR/.claude"
jq 'del(._comment)' "$REPO/lab/cressey-stubs/settings.cressey-hook.example.json" \
  | sed -e "s#CRESSEY_HOOK_URL#$URL#g" -e "s#CRESSEY_RUN_KEY#$KEY#g" > "$SETTINGS"

if [ "$(uname)" = Darwin ]; then open "$DASHBOARD"; else xdg-open "$DASHBOARD" >/dev/null 2>&1 || true; fi
echo "Cressey is watching $DIR. Dashboard: $DASHBOARD (admin key, asked once: $CRESSEY_ADMIN)" >&2
echo "Try: \"create notes.txt, then delete it with rm\". Cressey holds the rm on the dashboard." >&2
(cd "$DIR" && claude)
