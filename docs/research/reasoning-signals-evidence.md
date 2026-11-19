# Primary evidence measured on the team's machine, 2026-10-12

Measured in a Claude Code session on 2026-10-12, from local files and controlled headless probes. Content of user transcripts was never copied; only structure, counts and that session's own transcript were inspected. Tag: [PRIMARY], confidence H unless stated.

## 1. Claude Code 2.1.296 + Claude Opus 5.5: what the transcript records

Source: the measuring session's own interactive transcript (`~/.claude/projects/<repo>/68f11be7-....jsonl`), effort `max`.

- One API message is written as several JSONL lines, one per content block (`apiBlockIndex` 0..n), sharing `message.id` and the same final `usage`.
- Reasoning: a `thinking` block with empty `thinking` text and a signature of 1,040–27,716 characters. Signature length ≈ 4 × `thinking_tokens` (+ ~1,000): 27,716 / 6,981; 11,108 / 2,651; 3,548 / 898; 10,676 / 2,871.
- `usage.output_tokens_details.thinking_tokens` gives the exact hidden-reasoning count per message: 62 to 6,981 in this session (output_tokens 331 to 7,383). It includes the full (unsummarized) length of progress notes: messages with a progress note and no reasoning block still report 83–104 thinking tokens.
- `thinkingDurationMs` (per transcript line): 965–66,112 ms for reasoning blocks, 1–5 ms for progress-update blocks. Ratio ≈ 9.5–15.6 ms per thinking token (≈ 65–105 tokens/s). Duration is a noisier restatement of thinking_tokens (server speed, network), not new information.
- Other line fields: `thinkingDisplay` ("updates"), `effort` / `perTurnEffort` ("max"), `requestedModel`, `advisorModel`, `isSidechain`, `requestId`, `version`, `entrypoint`; usage has `service_tier`, `speed`, `inference_geo`, `fallback_credit`, `iterations`, cache fields.
- Between-tool notes: in this session a one-sentence note stayed a verbatim `text` block and every multi-sentence note became a second `thinking` block WITH text (a progress update, signature ≈ 1,100 chars). The probes in §3 show the split is not a fixed length rule: it varies by run.

## 2. Progress-update text is a paraphrase, and it can shift meaning

Comparison of the notes the measuring session wrote with what the transcript recorded (same session):

| Written by the model | Recorded progress update |
|---|---|
| "Skills loaded. The repo is Python + TypeScript. Before any research I need to know how Cressey handles "thoughts" today, so I'll recall project memory and read the existing reasoning specs and the code that ingests thinking." | "Skills loaded—this repo is Python + TypeScript. Before diving into research, I'll check project memory and review the existing reasoning specs and thinking-ingestion code to see how Cressey currently handles "thoughts."" |
| "Key finding from the spec: in the lab transcripts, all 29 thinking blocks are signed and empty, so today Cressey reads only the visible narration." | "I've confirmed all 29 thinking blocks in the lab transcripts are signed but empty, meaning only visible narration gets read." |

The second row upgrades a sourced claim ("from the spec") into a first-person verification ("I've confirmed") the model never made. Wording, hedges and attributions are not preserved. One-sentence `text` blocks were verbatim.

## 3. The MessageDisplay hook never carries thinking blocks (Claude Code 2.1.296)

Static evidence (strings of the shipped binary `~/.local/share/claude/versions/2.1.296`):
- MessageDisplay input schema: `turn_id`, `message_id` ("UUID ... Not the API msg_… id"), `index`, `final`, `delta` ("The newly completed lines since the prior flush"). "Display-only: the stored message and what the model sees are untouched." Flushes at most ~10/s, 3 in flight, 10 s timeout per flush.
- Completed-message path builds the delta from `content.map(M => M.type==="text" ? M.text : "")`; no text → no MessageDisplay event.
- Streaming path: thinking streams through a separate callback (`onStreamingThinking`); only streaming text goes through the MessageDisplay transform.
- Hook events in 2.1.296: PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch, Notification, UserPromptSubmit, UserPromptExpansion, SessionStart, SessionEnd, Stop, StopFailure (with `error`, `error_details`, `last_assistant_message`), SubagentStart, SubagentStop, PreCompact, PostCompact, PreModelSwitch, PostModelSwitch (sources command / picker / sdk / auto / resume), PermissionRequest, PermissionDenied, Setup, TeammateIdle, TaskCreated, TaskCompleted, Elicitation, ElicitationResult, ConfigChange, WorktreeCreate, WorktreeRemove, InstructionsLoaded, CwdChanged, FileChanged, DirectoryAdded, MessageDisplay.

Controlled probe (headless `claude -p`, Opus 5.5, effort medium by default, read-only tools, project-only settings, command hooks logging every payload; folder in the scratchpad, cost $0.63):
- The model emitted 3 multi-sentence progress notes (e.g. "release.md is just a one-line release checklist, not a changelog. Next I'll check docs/a.txt, expecting a short scratch note…") as `thinking` blocks with text, plus 2 `text` blocks (an opening one-liner and the final summary).
- MessageDisplay received only the 2 `text` blocks. None of the 3 notes reached any hook.
- Ordering, CORRECTED by direct measurement: the transcript lines' `timestamp` fields put each update and its `tool_use` 25–40 ms before PreToolUse, but those fields are creation times, not write times. A PreToolUse hook that read the file found the call's `tool_use` line NOT on disk (4/4 calls, probe 2). At PostToolUse it was on disk after a 680 ms Bash call, not after 30 ms Read calls (probe 3). A PreToolUse hook that polls the file every 50 ms saw the line land 105–108 ms after the hook started (3/3, probe 4): the write is asynchronous and not blocked behind the hook. So the note that introduces a call is readable at that call's PreToolUse only by waiting ~0.1–0.3 s; `docs/decisions.md` (10-11: "Claude Code writes a turn to the transcript only once its calls have returned") describes reading without waiting.
- Bash calls carry the agent's own one-line intent in `tool_input.description` at PreToolUse ("List files in the docs folder"), verbatim and bound to the call. Read calls carry only `file_path`.
- Channel choice is stochastic per run, same prompt and model (4 probes): probes 1–3 sent the first note of the turn as `text` (one had 3 sentences) and later notes as progress updates (80–209 chars); probe 4 sent every note (2–3 sentences) as `text` and no updates. MessageDisplay alone therefore covered between 2 of 5 notes (probe 1) and all notes (probe 4). Cost per probe $0.11–0.63; thinking_tokens per run 99–431.
- PreToolUse payload keys: cwd, effort, hook_event_name, permission_mode, prompt_id, session_id, tool_input, tool_name, tool_use_id, transcript_path (no model). Stop adds background_tasks, session_crons, stop_hook_active.
- The transcript file holds final per-message usage (thinking_tokens 11–179); `stream-json` stdout holds only partial per-message usage, with totals only on the final `result` line (missing when a run is killed: lab run 011950).

- `showThinkingSummaries: true` (probe 5: project settings, headless `-p`, Opus 5.5, one run): the transcript lines carried no `thinkingDisplay` field, reasoning blocks stayed empty, and the progress-update blocks (thinkingDurationMs = 1, right before each tool_use) came back EMPTY. The setting gave no reasoning summaries and removed the progress-update text, i.e. the "omitted" shape. Interactive behaviour not tested. A user or admin setting can therefore silence the update channel without any error.
- Bash tool input reaches Jev's floor labels whole: `policy.yaml` maps Bash to `{kind: shell, arg: command}` (the code floor reads only `command`), but `proxy._labelled` → `triangle.floor_labels` → `judgment_state(words=False)` shows `step.args`, the full redacted `tool_input` JSON including the agent-written `description`. The floor calibration set (`data/eval/floor-calibration.json`, 85 actions) contains no `description` field. Verified by reading the code, not by a live test.

## 4. Model dependence on this machine (structure counts, ~53k API messages, all local Claude Code transcripts)

| Model | API messages | text blocks | progress updates | empty reasoning blocks | thinking_tokens / message median, p90, max |
|---|---|---|---|---|---|
| claude-opus-5-5 | 39,087 | 14,087 | 4,527 | 25,665 | 119, 1,309, 50,307 |
| claude-opus-5 | 11,275 | 5,064 | 0 | 5,816 | 48, 861, 8,283 |
| claude-fable-5-1 | 1,534 | 493 | 46 | 1,083 | 231, 1,759, 15,864 |
| claude-opus-4-8 | 470 | 350 | 0 | 308 | 305, 3,306, 10,382 |
| claude-opus-4-6 | 179 | 122 | 0 | 87 | 0, 601, 16,961 |
| claude-sonnet-5-5 | 41 | 16 | 9 | 38 | 291, 3,224, 6,007 |

- Opus 5 and older: narration between tool calls arrives as verbatim `text` (MessageDisplay sees it). Opus 5.5 and Sonnet 5.5: multi-sentence notes move into paraphrased progress updates (MessageDisplay does not see them). Fable 5.1: very few updates.
- Hidden reasoning volume differs by model by an order of magnitude at the median; thresholds on it cannot be shared across models.

## 5. Cressey's own corpus and calibration (repo facts)

- All lab runs (`lab/runs/*`, 2026-10-11) used `claude-opus-4-6` via `claude -p --output-format stream-json`: narration is verbatim `text`; thinking blocks empty. Hidden reasoning per run: 396 (023759, the agent that paused and asked), 1,864 (005357), 2,272 (011045), 12,988 (pressure-112901). `duration_api_ms` / `duration_ms` = 0.97–0.99 (tool time is ~1–3% of wall time).
- `backend/data/eval/thoughts-calibration.json` (Task 8, jev-1.13.0, 40 runs, 412 thoughts) was calibrated on that Opus 4.6 narration, METR quotes and synthetic S9 runs. Benign p99: P1 0.98, N1 0.94, plan 0.95, R 0.59. Case file holds 9 of 21 incidents before harm with 2 false holds; findings: N1 high on plain narration (fixed by rewording), R links only through extracted objects, h03 has no words.
- `core/runs.py` tags every MessageDisplay message `source="narration"`; `core/hook.py` ignores `transcript_path`, `effort`, `tool_use_id` linkage to words, and every metadata field above.
