# S2: live model calls (2026-10-08)

The spike code was throwaway and has been deleted. The keys are in `cressey/.env`, which is git-ignored, and their values were never printed.

## Access verified
- **OpenAI:**
  - The key lists 133 models, including `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.5`, `gpt-5.5-pro`, `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra` and `gpt-4.1-mini`.
  - `text-embedding-3-small` was called and works.
- **Jev:**
  - `typesafe-sdk` 0.7.2, using `TYPESAFE_API_KEY` and the SDK's default base URL.
  - The response reports the model as **`jev-1.13.0`**.

## Results
| Test | Model | Latency | Result |
|---|---|---|---|
| Extracting ANSSI recommendations after undoing line-break hyphenation (`(\w)- (\w)` → `\1\2`) | none | none | **35/35** in French. BM25 alone found 27/35 without this fix |
| Embeddings, 35 passages (1,536 dimensions) | text-embedding-3-small | 3.1 s for the 35 | « validation humaine avant une action critique » → **R9 ranked 1st** (BM25 missed it). The same question in English → R9 ranked 3rd, with a tight margin (0.46 against 0.47). « journalisation et traçabilité » → **R29 « Journaliser l'ensemble des traitements » ranked 1st** (BM25 missed it). Rights → R35, R26, R10 |
| Incident → one French query and one English query (Pydantic structured output via `responses.parse(text_format=…)`) | gpt-5.4-mini | 2.7 s | Valid output; both queries usable |
| Re-ranking 4 passages for one question (4 yes/no questions in one call) | Jev jev-1.13.0 | 436 ms; 1,013 input tokens | R9 = **0.88**, R12 = 0.04, R30 = 0.16, R35 = 0.06. Clear separation, and French works |
| 2-step guide with verbatim quotes, checked by code | gpt-5.4-mini | 3.0 s | **2 of 2 quotes found** in the cited passage |
| "Is this action needed for the task?" (typo fix in README, 4 actions, 3 runs) | Jev jev-1.13.0 | 302–796 ms per call (4 questions) | read README 0.84, edit README 0.95, `run_tests` 0.15, `DROP TABLE` on production 0.01. **Stable across the 3 runs** (±0.01) |

## Edge cases and limits found
- **A harmless action can look like drift.** `run_tests` scored 0.15 for "needed" on a typo fix. So drift must never alarm on its own: weight it by the action's risk class, computed by code. For example, risk-weighted drift = (1 − needed) × risk, with read = 0, write = 0.5 and destructive = 1.
- **French question against English text is weaker** with `text-embedding-3-small`: the right passage ranks 3rd, with a margin of 0.01. Search in both languages: the LLM rewrites each query into French and English, then the results are merged by rank (reciprocal rank fusion).
- **Calibration is not measured.** Jev's scores look well separated here, but we have no labelled set yet. Plan a labelled set and an expected calibration error (ECE) measurement.
- **Latency:** Jev took 0.3–0.8 s per call and the LLM about 3 s. That's fine for the asynchronous guide. The inline path must never wait on the LLM: code rules first, Jev only on writes and irreversible actions.
- **Rate limits** are still not measured; sources say 1,200 requests per minute.

## What this changes in the plan
- **Retrieval:** ANSSI extraction with hyphenation undone (35/35), then BM25 plus embeddings in French and English, merged by rank, then Jev re-ranking with a threshold (for example ≥ 0.5; calibrate it on the labelled set).
- **Drift:** compute it by risk class, never alarm on drift alone.
- **Models:**
  - guides with `gpt-5.4-mini`, after checking quality against `gpt-5.5`;
  - typed decisions with Jev `jev-1.13.0`;
  - embeddings with `text-embedding-3-small`.
- **Pin the model versions** in the config.
