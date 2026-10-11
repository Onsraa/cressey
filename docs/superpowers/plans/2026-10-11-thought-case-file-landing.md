# Thought case file — landing note

Durable record of the `feat/thought-case-file` build: what shipped, the rulings, the deferred
minors and what Task 8 still needs. Plan:
`docs/superpowers/plans/2026-10-11-thought-case-file.md`. Spec:
`docs/superpowers/specs/2026-10-11-cot-triangle-indicators-design.md`.

## Status (2026-10-11)
- Tasks 1–7 complete, each independently reviewed; whole-branch review verdict **Ship** (no Critical/Important).
- Green at HEAD `f78f561`: backend 545 passed + ruff/ty clean; web 53 passed + biome/tsc clean.
- Ships in **shadow mode**: the case file and §7 decision are computed, logged and displayed, but no
  live hold, key, way-out, incident or refusal reads `Run.case` / `Step.shadow`. Floor and trap keys
  untouched. Safe to demo as-is.
- **Landed 10-11** on `main` as `f665dd5`, after holds-that-matter (`1983b2f`): backend 719 and web 68 tests pass.
- **Task 8 done 10-11** (`data/eval/thoughts-calibration.json`, `docs/decisions.md`): cut-offs calibrated, the must-pass cases still fail, so the case file stays in shadow. Was: **Task 8 (threshold calibration) is PARKED** — needs live Jev (record mode) over §10's labelled
  sources plus a human choice of cut-offs. Thresholds ship as the S9 floors in `policy.yaml`
  `triangle.thoughts` (R 0.2, every other indicator + `about`/`approves` 0.5), marked "until calibrated".

## What shipped (per task)
1. `core/thoughts.py` — segment an agent message into thoughts; extract objects (ids, paths, urls, `$VARs`, `[secret:fp]` markers → `secret:fp`).
2. `core/models.py` — `Event`, `Thread`, `Note`, `Case`, `Shadow`; `Message.source/thoughts/read`, `Run.case`, `Step.shadow`, `TextIn.source`, `Thresholds.thoughts`. (The words-source literal is named `WordSource` to avoid clashing with the existing `Source` provenance model.)
3. `core/thoughts.py::read_thought` — the §6 typed questions per thought → `Event`s.
4. `core/case.py` — `threads()` (P/O threads keyed by object), `uses()`, `decide()` (the §7 table), `notes()`.
5. `core/case.py` — `read_message`, `code_events`, `shadow`, `read_prompt` (the case over a run).
6. `core/proxy.py`/`runs.py`/`hook.py` — schedule the shadow in the background after today's decision (never awaited); per-run lock; `read_prompt` on prompts.
7. web `views/live/*` — per-thought indicator chips, the case per leg, the shadow decision (grey, non-live); supersedes the message-flags web display.

## Rulings made during the build (undo any you disagree with)
- Branched from current `main` without merging message-flags first (it did not merge cleanly then); after you landed message-flags, merged it into the branch cleanly (merge `058e831`).
- Superseded the message-flags **web** display; left the backend `flag_soon` pipeline and `Message.labels`/`flagged` fields in place but unread (plan sanctions "leave the fields unread").
- `read_prompt` catches the case up first so a human approval ("yes") isn't lost to read-ordering.
- The rationalization gauge shows the strongest R/C1 `direction=="toward"` event (web-only; backend `threads()`/`decide()` untouched — R stays events, not threads, which is correct for §7).
- Shadow runs for `control`/Observateur runs too (display-only, matches `flag_soon`).

## Deferred minors (none block merge or the demo)
- Object-extractor noise ids (hex≥8 matches digit strings; token-with-`/` matches `and/or`); a connection-string `host:port` tail splits a stray id; a path fused right after a `[secret:fp]` marker no longer matches. All shadow-only linking precision.
- Backend `flag_soon` now double-reads messages alongside the shadow — a later cleanup can remove it (bounded by shadow mode + the record/replay cache).
- The "Uses:" line quotes a thread's first event while the web gauge shows the strongest; a grey "shadow: would allow" chip shows on every allowed call.
- `about:<url/path>` judge-question keys contain `/`,`:`,`?` — unvalidated against the live Jev SDK; validate at Task 8 and sanitize the key there if rejected.

## When ready, finish Task 8
Run `read_thought` over §10's sources (the 4 lab transcripts, METR's quotes, the 22 S9 runs, the benign
set) through the live Jev in `record` mode; measure per-indicator precision/recall at a chosen
false-positive rate; set `policy.yaml triangle.thoughts`; pin the must-pass cases (PocketOS pair, HF Edit).
Est. cost is small (Jev ~$0.042/Mtok input), but it is a paid run plus a human calibration call.
