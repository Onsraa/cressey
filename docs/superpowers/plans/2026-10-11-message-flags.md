# Message Flags on the Triangle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jev flags each agent message as it arrives. The dashboard shows those flags on the Message row and as a "from the agent's words" value on P and R, without changing any hold, confirmation or measured number.

**Architecture:** One background Jev call per finished message, asking the S9 ledger's own questions, stored on the `Message`. Before a call's legs are computed, Cressey awaits the flags of the messages said before it and fills a new display-only `Leg.words`. The dashboard draws `max(score, words)` and tags the value when the words lead.

**Tech Stack:** FastAPI, Pydantic, typesafe-sdk (Jev), React, Bun.

**Spec:** fix 2 as agreed in chat on 2026-10-11; `docs/concept.md:40` ("The reasoning, when available, only sharpens the score"); `docs/decisions.md:43` (the hold rule this plan must not touch).

**Branch:** `feat/message-flags` from `main`.

## Global Constraints
- `Leg.score` and `Leg.confirmed` are computed exactly as today. Only the dashboard reads `Leg.words`: not holds, the way out, the read-only key, incidents, nor `demo/measure.py`.
- The questions are `LABELS["pressure"]`, `LABELS["rationalization"]` and `LABELS["manipulation"]` from `core/triangle.py`, verbatim. Jev sees the ledger's window without the action: `{"task", "mandate", "note": NOTE, "current_step": {"agent_said": [part]}}`.
- `P.words` = pressure. `R.words` = max(rationalization, manipulation). `O.words` stays None.
- Words only raise what is shown, never lower it: `renounces` is not used.
- Jev reads only the message's redacted text (`Message.text`).
- A `visibility: "tools"` run flags nothing ("Cressey scores tool calls only").
- `demo/measure.py` doesn't flag messages, so the evaluation is unchanged.
- UI copy: "from the agent's words". No new dependency. Commits carry no co-author line.

## Review Focus
1. A streamed message never marked `final`: never flagged, and no call waits on it.
2. Jev answers nothing, or a replay-mode miss (`NotRecorded`): `labels` stays None, `words` None, and the call is neither failed nor held.
3. Several calls after one message: they await the same task; one Jev call per message.
4. A message longer than `CHUNK`: read in parts with `_max_over_parts`; each flag is the max.
5. A hook run created with `visibility: "tools"` still receives messages: none is flagged, every `words` stays None.

---

### Task 1: Flag messages and fill `Leg.words` (backend)
**Files:** modify `backend/src/cressey/core/models.py` (`Leg` :103, `Message` :163), `core/triangle.py`, `core/runs.py` (`say` :116, `stream` :121), `core/hook.py:57-64`, `core/api.py:97-102`; regenerate `backend/openapi.json`. Tests: `backend/tests/core/test_triangle.py`, `backend/tests/core/test_hook.py`.

**Interfaces (produces):**
- `Message.labels: dict[str, float] | None = None` and `Message.flagged: list[str] = []` (both served): `"pressure"` and/or `"rationalization"` when a label reaches its `FLOORS` value (manipulation counts as rationalization).
- `Leg.words: float | None = None`.
- `triangle.WORDS: dict[str, Noul]`: the three questions above.
- `triangle.flag_soon(run: Run, m: Message, judge: Judge) -> asyncio.Task[None] | None`: starts the flagging once per message, like `label_soon`; None for a `"tools"` run.
- `legs()` and `read_after()` first await the flagging of every message with `after < call.n`, then set `words` to the max over those messages.
- `Runs.say()` returns its `Message`. `Runs.stream()` returns the `Message` when `final`, else None.

- [ ] Write the failing tests (with `FakeJudge` answering the three questions):
  - `test_words_raise_p_not_its_score`: message pressure 0.9, then a read → `pressure.words == 0.9`, `pressure.score == 0.0`, `not pressure.confirmed`.
  - `test_words_never_hold_a_read`: rationalization 0.95 → `rationalization.words == 0.95`, `not rationalization.confirmed`, `alarm(legs, "read") is False`.
  - `test_words_leave_a_write_unchanged`: the same write with and without flagged messages → equal `score` and `confirmed` on every leg, equal `alarm`.
  - `test_manipulation_counts_for_r`: manipulation 0.8, rationalization 0.1 → `rationalization.words == 0.8`, `m.flagged == ["rationalization"]`.
  - `test_no_answer_leaves_words_none`: the judge returns None, then raises `NotRecorded` → `m.labels is None`, `words is None`.
  - `test_one_flag_call_per_message` and `test_legs_waits_for_a_flag_in_flight` (a judge that answers after a delay → `words` is set).
  - `test_a_long_message_is_read_in_parts`: 2 × `CHUNK` characters, the pressure sentence in the second half → `labels["pressure"]` is that part's answer.
  - `test_tools_run_flags_nothing`: `visibility="tools"` → `flag_soon` returns None, `words is None`.
  - `test_hook.py::test_message_flagged_once_when_final`: deltas without `final` → no flag call; then `final` → one.
- [ ] Run `cd backend && uv run pytest tests/core/test_triangle.py tests/core/test_hook.py -q` → the new tests fail.
- [ ] Implement. `hook.py` calls `flag_soon` on a final message and `api.py` after `runs.say`, both with `request.app.state.judge`.
- [ ] `uv run pytest -q` passes in full; `uv run ruff check . && uv run ty check` clean; `uv run python -m cressey.export_openapi`.
- [ ] Commit.

### Task 2: Show the flags (web)
**Files:** `web/src/api/schema.d.ts` (`bun run gen:api`), `web/src/lib/labels.ts`, `web/src/views/live/run.ts` (`agg` :125), `Center.tsx`, `LiveView.tsx:129-154`, `Chart.tsx:114-123`, `Trace.tsx`, `Inspector.tsx`. Tests: `web/src/views/live/run.test.ts`, `web/src/views/live/LiveView.test.tsx`.

**Interfaces:** consumes `Leg.words`, `Message.labels`, `Message.flagged`. Produces in `labels.ts`: `level(leg) = Math.max(leg.score, leg.words ?? 0)` and `byWords(leg) = (leg.words ?? 0) > leg.score`.

- [ ] Failing tests: `agg` keeps the max `words` over calls; a gauge with `score 0`, `words 0.9` reads `0.90` with "from the agent's words"; a Message row with `flagged: ["pressure"]` shows a lit P chip and an unlit R chip; the triangle point and the Across-steps chart use `level()`.
- [ ] Implement with the existing P/O/R chips and `Bar`. A selected Message shows its three labels as bars in the Step panel.
- [ ] `bun run ci` passes. Commit.

### Task 3: Check on real runs
- [ ] Replay METR (`python3 -I lab/replay_hf.py`) and PocketOS (`python3 -I lab/replay_hook.py --transcript lab/runs/20261011-011950-1/transcript.jsonl`, then reject step 11): flags on the right Message rows; holds unchanged (METR step 3 "protected path", PocketOS step 11 "trap key"). Screenshot both.
- [ ] Flag the messages of S9's normal runs (`docs/test-results/s9_runs.json`) with a throwaway script, as S9 did. Report how many reach `FLOORS`. Report only; no threshold is moved.
- [ ] Run the stage scenarios once so the new questions are in the judge cache, then check that a second run has 0 cache misses. Add a `docs/decisions.md` line.
