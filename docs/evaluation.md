# Evaluation

## Method
- **Data** (`backend/data/eval/`):
  - `retrieval.json`: 33 dev questions. 31 have an expected passage; 2 are out of scope, and the right answer for those is « je ne sais pas ».
  - `incidents.json`: 8 incidents, one of which (`i8`) contains text that tries to steer the writer.
- **Hit@3** checks whether the expected passage is in the top 3, at three stages: BM25 alone, hybrid search, and after Jev re-ranking. `anssi-fr:Rn` and `anssi-en:Rn` count as the same passage.
- **Citation validity:** steps kept divided by steps written.
- **Held-out set:** written by someone outside the team, run once after the Sunday 06:00 freeze, with misses reported. Not written yet.
- **Command:** `cd backend && uv run python -m cressey.guide.eval --split dev`.

## Dev results (2026-10-10, live models)
| Metric | Result |
|---|---|
| Hit@3, BM25 alone | 26/31 (84%) |
| Hit@3, hybrid | 30/31 (97%) |
| Hit@3, after re-ranking | **31/31 (100%)** |
| Out-of-scope questions answered « je ne sais pas » | 1/2 |
| Incidents with a sourced guide | 8/8 |
| Citation validity | **100%** |
| Steering case `i8` | No step cited a passage outside the list |
| Latency per incident, live | p50 9.0 s, p95 12.3 s |
| Latency per incident, `replay` | p50 1.2 ms. Results identical to live, with the keys blanked |

**Report file:** `backend/data/eval/report-dev.json`.

## Known weak points
- **One of two out-of-scope questions got passages anyway.** The threshold plus the « je ne sais pas » path limit the effect.
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
