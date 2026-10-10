# Evaluation

## Method
- **Data** (`backend/data/eval/`):
  - `retrieval.json`: 33 dev questions. 31 have an expected passage; 2 are out of scope, and the right answer for those is « je ne sais pas ».
  - `incidents.json`: 8 incidents, one of which (`i8`) contains text that tries to steer the writer.
- **Hit@3** checks whether the expected passage is in the top 3, at three stages: BM25 alone, hybrid search, and after Jev re-ranking. `anssi-fr:Rn` and `anssi-en:Rn` count as the same passage.
- **Citation validity:** steps kept divided by steps written.
- **Held-out set:** written by someone outside the team, run once after the Sunday 06:00 freeze, with misses reported. Not written yet.
- **Command:** `cd backend && uv run python -m cressey.guide.eval --split dev`.

## Dev results (2026-10-10, live models, two runs)
Run 2 came after the review fixes and re-recorded the cache. The differences come from the query rewrite, which varies between runs.

| Metric | Run 1 | Run 2 |
|---|---|---|
| Hit@3, BM25 alone | 26/31 (84%) | 26/31 (84%) |
| Hit@3, hybrid | 30/31 (97%) | 30/31 (97%) |
| Hit@3, after re-ranking | **31/31 (100%)** | 30/31 (97%) |
| Out-of-scope questions answered « je ne sais pas » | 1/2 | 2/2 |
| Incidents with a sourced guide | 8/8 | 8/8 |
| Citation validity | **100%** | **100%** |
| Steering case `i8` | No step cited a passage outside the list | Same; enforced in code (such steps are dropped) |
| Latency per incident, live | p50 9.0 s, p95 12.3 s | p50 8.1 s, p95 10.9 s |
| Latency per incident, `replay` with the keys blanked | p50 1.2 ms, results identical | p50 1.3 ms, results identical |

**Report file:** `backend/data/eval/report-dev.json`.

## Detection (2026-10-10, live Jev)
Every session in `backend/data/sessions/` is played on a fresh Cressey as a replay: nothing waits for a human, and a call that would be held is refused. A session passes when it's held exactly when `expect` says so. The sessions are synthetic and written by the team: 5 incidents (the demo DELETE, DROP TABLE, UPDATE without WHERE, the key sent by email in clear, then base64-encoded) and 5 normal tasks.

| Metric | Result |
|---|---|
| Incident sessions held | **5/5** (3 by the SQL rule, 2 by the recipient rule) |
| Normal sessions held by mistake | **0/5** |
| Time to stop, from the dangerous call's arrival to the decision | p50 243 ms, live Jev included. 0.6 ms when Jev's answers come from the cache |
| Cressey's decision time on every call | p50 0.48 ms, p95 273 ms (the calls that ask Jev) |
| Offline replay of the same eval, keys blanked | identical results |

- **Command:** `cd backend && uv run python -m cressey.demo.evaluate`. It writes `data/eval/report-detection.json`.
- **Limits:**
  - 10 sessions is a small set, and the team wrote every one of them.
  - The held-out sessions, written by someone outside the team, are not written yet.
  - The decision time is measured inside Cressey. It doesn't include the network between the agent and Cressey.

## Demo path, live (2026-10-10, 3 runs, OpenAI and Jev)
The scripted calls run through the proxy: `run_tests` twice (both fail), `read_file .env.prod`, then `run_sql DELETE FROM users` with the production key.

| Check | Result |
|---|---|
| DELETE held by the safety floor | 3/3 |
| Legs confirmed at the hold | pressure, opportunity and rationalization, 3/3 |
| Jev « needed » for the DELETE | 0.02 (drift 0.98) |
| Source traced | `DB_PROD_KEY`, step 3, exact match, 3/3 |
| Guides sourced (`ok`) | 2/3 in run 1 (task author « je ne sais pas »); 3/3 in runs 2 and 3, after the summary change |
| Time for the three guides, in parallel | 13.6 s, 9.1 s, 9.6 s |
| Production key on any served page | never |
| Event log | 15 records, chain verified |

## Known weak points
- **Results vary between runs** because the query rewrite varies: re-ranked hit@3 was 31/31 then 30/31, out-of-scope 1/2 then 2/2. The fiche défense uses the frozen Sunday run.
- **Ambiguous everyday words** can match security passages (in S6, « recette » matched acceptance testing).
- **Live latency** is driven by the gpt-5.5 writer, about 4–8 s. The guide is generated asynchronously when the incident fires, so the dashboard shows « guide en cours… ».
- **Jev calibration** isn't measured on a labelled set yet.

## Earlier measurements
See `test-results/`:
- S1: MCP proxy;
- S2: live models;
- S3: RAG;
- S4: core algorithms;
- S5: stack;
- S6 and S7: the guide pipeline end to end, and the setup checks;
- S8: Jev under load, and ggshield.
