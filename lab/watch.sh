#!/usr/bin/env bash
# Follow an agent run as it happens, readable and with the lab tokens hidden, so it can be
# screen-recorded. Defaults to the latest run. Ctrl+C to stop.
#
#   bash lab/watch.sh                 # the latest run, live
#   bash lab/watch.sh lab/runs/<stamp> --once   # print it once, no follow
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$LAB_DIR")"
run="${1:-$LAB_DIR/runs/$(ls -t "$LAB_DIR/runs" | head -1)}"
follow=-f; [ "${2:-}" = --once ] && follow=

# eval, not `. <(…)`: bash 3.2 (macOS) sources nothing from a process substitution.
eval "$(grep '^RAILWAY_LAB_' "$REPO_DIR/.env" | tr -d '\r')"

# Tokens are hidden before anything is cut short, so no part of one reaches the screen.
tail -n +1 $follow "$run/transcript.jsonl" | jq --unbuffered -r \
  --arg trap "$RAILWAY_LAB_TRAP_TOKEN" --arg staging "$RAILWAY_LAB_STAGING_TOKEN" '
  def hide: tostring | gsub($trap; "<old ops token>") | gsub($staging; "<staging token>");
  if .type == "assistant" then
    .message.content[]
    | if .type == "text" then "\nAGENT  " + (.text | hide)
      elif .type == "tool_use" then
        "  RUN  " + .name + ": " + ((.input.command // .input.file_path // .input) | hide | .[0:700])
      else empty end
  elif .type == "user" then
    .message.content[]? | select(type == "object" and .type == "tool_result")
    | "  OUT  " + ((.content | if type == "array" then map(.text? // "") | join(" ") else . end)
                  | hide | gsub("\n"; " ") | .[0:300])
  elif .type == "result" then "\nDONE   " + ((.result // "") | hide)
  else empty end'
