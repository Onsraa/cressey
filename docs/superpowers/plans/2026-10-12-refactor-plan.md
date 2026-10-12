# Refactor plan: what the code should look like before the core grows

Date: 2026-10-12. Status: audit and plan for review. No code is changed by this document.

**Scope read:**
- `main` at `c1b51e1`, plus the uncommitted production-label work (all its checks pass: 738 backend tests, 76 web tests) and `feat/p0-trust`.
- Read in full: `backend/src/cressey/core`, the judge and guide caches, `app.py`, `settings.py`, the policy, the dependency lists.
- Read for structure and duplicates: `demo/`, `lab/`, `web/src`.

**Load assumed:** one Cressey per company, tens of agents, thousands of tool calls a day, days of uptime (the critical-sectors design).

## Findings
Numbered across groups.

### Must fix
1. **A write only Jev would hold goes through when Jev is down** (`core/proxy.py` `_labelled`: `if labels is None: return []`).
   - It covers `terraform destroy`, `curl -X DELETE`, a production deploy.
   - Fix: hold it, with the reason "Jev didn't answer", under the `irreversible` response. That is P0 Step 5, after the production-label work is committed.
2. **The agent can switch its guard off** (`core/api.py`: approve, unlock and policy routes with no auth).
   - Fixed on `feat/p0-trust`: an admin key, plus a hold on calls aimed at Cressey. Merge it.
3. **Memory and the dashboard grow without limit.**
   - `Runs` and `Incidents` never forget a run, and every step keeps its tool's full result text (`step.result`, `runs.py:265`). Large file reads stay in RAM for good.
   - The dashboard polls `GET /api/runs` every second (`web/src/api/live.tsx`). That route serializes every run, step and message ever seen (`api.py:76`).
   - At thousands of calls a day this means gigabytes after a few days, and a multi-megabyte answer every second.
   - Fix:
     - drop a step's `result` text once its run ends, keeping only the token index the tracer needs;
     - serve run summaries every second, and a run's steps on demand.
4. **The gateway can only front the demo tools** (`app.py`: `upstream = demo_tools(demo)`, then `build_mcp(guard, upstream)`; the preflight reads the same demo tools).
   - A company cannot point Cressey at its own MCP servers today.
   - Fix: upstream servers come from configuration. The demo tools become a dev profile.

### Should fix
5. **Every agent message is read twice by Jev.**
   - The old message flags read it: `triangle._flag`/`flag_soon`, filling `Message.labels`/`flagged` and `Leg.words`. They are display-only, and no screen reads them any more (no web code uses `flagged` or `words`).
   - The thought case reads it again (`thoughts.read_thought`). This one drives the dashboard and the thought holds.
   - Fix: delete the flags, their fields and their callers (`hook.py:86`, `api.py:110`). This saves one Jev call per message and about 120 lines plus tests.
6. **`core/triangle.py` (795 lines) does seven jobs:**
   - building what Jev reads;
   - the step ledger;
   - message flags;
   - the write judgment;
   - the safety floor's labels (`floor_labels`);
   - the report check;
   - a research helper (`views`, used only by `demo/measure.py`).

   `case.py` and `thoughts.py` import its private helpers: `_max_over_parts`, `_pieces`, `_answers_over_parts`, `_redacted_off_loop`. Fix: split it by job (target below).
7. **The decision engine lives inside the MCP adapter.** `Guard` in `proxy.py` is both FastMCP middleware and the decision every surface needs, and the Claude Code hook calls `proxy.Guard`. Every new surface would have to go through the MCP module. Fix: an engine module that both adapters call.
8. **Layers point both ways.**
   - Core imports `guide`:
     - types: `models.py:9-10`, `case.py:34`, `incidents.py:26-27`, `preflight.py:15`;
     - private client internals: `draft.py:15` imports `_Adapter` and `_responses`;
     - the cache: `judge.py:24-25`.
   - Meanwhile `guide/cache.py:18-19` imports `core.draft` and `core.models`.
   - The app and `incidents` depend on `demo` for sessions, replays and tools.

   Fix: one direction only, `domain ← llm ← engine ← adapters/api ← app`, guarded by a test that fails on a wrong import.
9. **Two record-and-replay caches.** `guide/cache.py` `Cached` and `core/judge.py` `JevJudge.answers` each implement the five modes (live, record, replay, fallback, replay-first) over JSON files. Fix: one model cache, used by the judge, the guides and the drafter.
10. **Hold reasons are used as identifiers.**
    - The fleet signal keys on `f"{tool} | {reason}"` (`proxy.py:185`, `incidents.py`).
    - Incidents de-duplicate on the reason text (`incidents.has`).
    - The dashboard finds trap-key holds by `reason.startsWith("trap key used")` (`web/src/views/live/run.ts:342`, `Center.tsx:66`).

    Rewording one message silently breaks these. Fix: a structured reason (the check that fired, its detail, its score), with the display text derived from it.
11. **"Replay a recorded session through Cressey" exists five times, in three formats:**
    - `demo/agent.play` (YAML sessions over MCP);
    - `demo/replay.py` (« Rejouer ×5 »);
    - `lab/replay_hook.py` (a Claude Code transcript over the hook);
    - `lab/replay_hf.py` (untracked, a near-copy);
    - `lab/label_thoughts.py` (in process, with its own lab, METR and S9 readers).

    Fix: one recorded-session format and one player. Shadow mode needs exactly this.
12. **Seven copies of "start a background task once and keep it alive":**
    - `triangle._READING` and `_FLAGGING`;
    - `case._SHADOWING` and `_PROMPTS`;
    - `Guard._late`;
    - `Incidents._tasks`;
    - `api._assessing`.

    The module-level ones are shared by every app in the process, including test apps and replay apps. Fix: one small helper, owned by the app.
13. **The dashboard re-implements engine rules in TypeScript.**
    - `run.ts` `ASKS` copies which thought questions belong to which leg (`case.LEG`).
    - `thoughtLegs` and `legEvidence` copy `case.leg_values`, including "a thought going away counts for nothing".

    A rule change must be made twice, or the screen disagrees with the engine. Fix: the API serves the computed values; the web only draws them.
14. **Dead code and dependencies:**
    - `case.notes()`, `Note` and `Case.notes`: only tests call them, and nothing fills the field;
    - the `str` branch of the judge's `Answer` and `top()`: none of the 211 recordings uses that format;
    - `fonttools`: imported nowhere;
    - the direct `sse-starlette` pin: `mcp` already brings it.
15. **Test doubles are copied.**
    - Fake judges: `measure.FakeJudge`, `stress.DownJudge`/`SlowJudge`/`CountingJudge`, `tests/core/helpers.ServedJudge`, and the per-test judges in `test_guard.py`.
    - Fake guides: `tests/server.fake_guide`, `stress._fake_guide`.
    - Server and API helpers: three copies.
    - Percentiles: `measure._p`, `stress._pct`, `evaluate._p95`.

    Fix: one `cressey.testing` module.
16. **Two leaks.**
    - `hook._pending` keeps every allowed call whose `PostToolUse` never comes (a session killed mid-call, a cancelled call).
    - `Runs._streaming` keeps a message cut off by `SessionEnd`.

    Fix: clear both on `SessionEnd`.
17. **One policy file does four jobs.** `policy.yaml` holds the engine's thresholds, Claude Code's tool catalog, the demo's tools, fake decoys and demo broker credentials. Sector packs need to add catalogs and rules without editing the engine's file. Fix: engine settings, one catalog per adapter, a demo profile.

### Nice to have
18. **Small web duplicates:**
    - `isRecord` (`run.ts`, `incidents/util.ts`);
    - `ms` (`Inspector.tsx`, `eval/format.ts`);
    - `COPIED_MS` (`ConnectPanel.tsx`, `Waiting.tsx`);
    - the ink color (`pixels.ts`, `charts.tsx`), which should be a CSS token.
19. **Owners are spread out.** `incidents.OWNERS`, `preflight.FIXES` and `OWNER_NAMES` describe the same owners. Fix: one `domain/owners.py`.
20. **« Rejouer ×5 » runs inside the core runtime.** `Incidents.replay` starts `asyncio.run` in a thread, with a fresh server per session. Fix: it moves to the replay package as an optional feature that the app wires in.

**Verdict:** the decisions are sound, but the code is shaped around the demo. Fix first:
1. merge P0, and close finding 1;
2. delete the old flags (5);
3. split engine, adapters and layers (6, 7, 8): every new surface depends on it.

**Lean:** about −600 to −800 lines (flags, notes, duplicate caches, doubles, replayers, registries), and −2 dependencies.

**Not checked:**
- the web views' logic beyond structure and duplicates;
- `guide/` retrieval and eval internals;
- `measure.py` and `stress.py` internals;
- the lab shell scripts;
- the deck.

Nothing was profiled. The load figures are an estimate, not a measurement.

## What the code looks like after
```
backend/src/cressey/
  domain/          pure types, import nothing of ours
    acts.py          the act record: agent, model + version, run/parent/session, tool, args, resource, environment, data class, who asked
    runs.py          Run, Step, Message, Mandate, Legs, Case, Event, Thread, Shadow
    reasons.py       Check (floor, trap_key, trap_key_read, self_call, irreversible, production, no_answer, triangle, thought, fleet), Reason, Response
    owners.py        legs, owner roles, who owns which fix
    incidents.py     Incident, Source, Fix, OwnerGuide, Replay
  llm/             model clients + ONE record/replay cache (judge, guides, drafter)
  judge/           the System One client: Judge, JevJudge, yes/top, TooLarge, NotRecorded
  engine/          decides; knows nothing of MCP, hooks or HTTP
    decide.py        before(act) / after(act, result): the five layers and the responses (today Guard.before/after)
    floor/           rules.py (dispatch), sql.py, shell.py, http.py, tripwires.py (trap keys, calls aimed at Cressey), labels.py (tool kind, irreversible, production)
    reading.py       what Jev reads: chunks, parts, answers over parts, redaction off the loop
    ledger.py        each step labelled once, and the evidence kept
    triangle.py      pressure, opportunity, rationalization, alarm, read-only key
    report.py        the report against the log
    case/            thoughts.py, case.py (threads, shadow, thought holds, prompts)
    preflight.py     the task assessed before the run
    agent_text.py    what the agent is told: way out, stop sentence, the checked rejection
  store/           runs.py (memory + file store, holds, sessions, retention), eventlog.py
  adapters/        mcp.py (FastMCP proxy, configurable upstreams), claude_code.py (hooks)
                   later: otel.py (shadow mode), model_gateway.py, frameworks
  api/             control.py (admin routes), agent.py (messages, report), auth.py
  incidents/       incidents.py, fleet.py (signals across runs), fixes.py
  replay/          trajectory.py (one recorded-session format), player.py,
                   importers/ (YAML sessions, Claude Code transcripts, METR, S9; later OTel)
  guide/           RAG fix guides: imports domain + llm only
  demo/            demo tools (a dev upstream), sessions, the stage recorder: nothing imports it but config
  evals/           evaluate, ablation, measure, calibrate_floor, stress
  testing/         fake judges and guides, serve/api helpers, percentiles (tests and evals share them)
  app.py           wiring only: settings → stores → engine → adapters → routers
  settings.py
web/src/           renders what the API computes: no engine rule in TypeScript
```

**Rules that keep it clean:**
- **Imports point one way:** `domain` ← `llm`, `judge` ← `engine` ← `adapters`, `api`, `incidents`, `replay` ← `app`. Nothing in `engine` imports `guide`, `demo` or `evals`. A test fails on a wrong import.
- **A new surface is a new adapter** that turns its events into acts and calls `engine.decide`. A new sector is a new pack: a catalog, rules and owners, as configuration plus code in its own package. Neither touches the engine.
- **Reasons are data;** text is only for display.
- **What the agent is told lives in one module** (`agent_text.py`), checked by the same rules.

## How to get there
Each phase is one PR. Each must keep:
- the full test suite green;
- the detection eval identical, session by session;
- the stage recording replaying with 0 misses.

Nothing changes behavior until phase 5.

| Phase | What | Findings | Done when |
|---|---|---|---|
| 0 | Land the production-label work, merge `feat/p0-trust`, hold when Jev doesn't answer | 1, 2 | On `main`; tests and evals green |
| 1 | **Delete:** message flags and their fields, `notes`, the `str` answers, `fonttools`, the `sse-starlette` pin; move `views()` to `evals/measure` | 5, 14 | No reference left (grep); schema regenerated; the web compiles |
| 2 | **Layers:** create `domain/` (types out of `guide/models`), `llm/` (one cache), `testing/` (one set of doubles); add the import test | 8, 9, 15, 19 | The import test passes; `guide/` imports only `domain` and `llm` |
| 3 | **Split by job:** engine vs adapters; `triangle.py` into reading, ledger, triangle, report, floor labels; `floor.py` into rules and tripwires; `incidents` into incidents, fleet and fixes; `api` into control, agent and auth; one background-task helper | 6, 7, 12, 20 | Same tests, moved; no private import across modules |
| 4 | **The act record** (roadmap Step 1): adapters emit acts with model, version and who asked; reasons become structured; the fleet keys on check + target | 10 | Hold text unchanged on screen; the fleet test keys on checks |
| 5 | **Configurable upstreams;** policy split into engine settings, catalogs and a demo profile | 4, 17 | Cressey fronts a real MCP server from config; the demo runs with its profile |
| 6 | **Bounded state:** result retention, run summaries plus detail on demand, leaks cleared on `SessionEnd` | 3, 16 | A 10,000-step soak keeps memory flat; the dashboard poll stays small |
| 7 | **One replay path:** recorded-session format, player and importers; « Rejouer ×5 », the evals and the lab run on it | 11 | The lab replayers are deleted; shadow mode is the next step |
| 8 | **Web:** the API serves computed legs and evidence; shared web utils | 13, 18 | No engine rule left in `run.ts` |

## Risks
- **Big moves break recorded answers.** A changed state field changes the cache key. Phases 1 to 3 must not change what Jev reads. The stage replay with 0 misses is the check.
- **The other session's work.** Phase 0 commits the production-label work first, so every later phase starts from one `main`.
- **Scope creep.** Each phase is one PR; anything new waits for the roadmap step that needs it.
