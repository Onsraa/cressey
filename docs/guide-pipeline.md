# Guide pipeline

Turns an incident into a fix guide in French. Every step cites a passage from a pinned corpus, quoted verbatim, and code checks the quote. When the sources don't cover the case, the pipeline says so instead of inventing.

## Input and output
- **In:** `GuideIncident(id, leg, owner_role, summary, source)`, with:
  - `leg`: `pressure`, `opportunity` or `rationalization`;
  - `owner_role`: `key_owner`, `task_author`, `platform_owner` or `soc`.
- **Out:** `Guide(id, incident_id, status, message, steps, passages, dropped_steps)`.
  - `status`: `ok`, `unsure` or `unavailable`;
  - each step is `GuideStep(action, source_id, quote, source_title)`.

## Steps
1. **Rewrite** (gpt-5.4-mini, `PROMPT_REWRITE_INCIDENT_V1`): the incident becomes one French query and one English query. The prompt defines the triangle's three legs.
2. **Search** (`retrieve.py`): three queries (French, English, raw text), each through BM25 and through embeddings, which makes 6 ranked lists. They're merged by reciprocal rank fusion (`k = 60`), keeping the top 8. If a query embedding fails, that search continues with BM25 only; the next search tries embeddings again.
3. **Re-rank** (Jev `jev-1.13.0`): one yes/no question per passage (« The passage directly answers the question »). Passages scoring under **0.4** are discarded.
   - **Switching to Strands Decider 2B** (decided 10-10): the same question goes to the local server. The 0.4 threshold was set on Jev's scores, so set it again on the dev set (the S6 method: count expected passages kept against others kept). Then re-run the eval and re-record the cache, since the model name is part of the cache key.
4. **Write** (gpt-5.5, `PROMPT_GUIDE_V1`): at most 4 steps. Each cites one passage id and a verbatim quote of 8–20 words. The incident text sits between `<incident>` tags and is treated as data, never as instructions. `<`, `>` and `&` in it are escaped, so it can't close the tag.
5. **Check, in code:** a step is kept only if its `source_id` is among the passages given to the writer and its quote appears in that passage. Matching ignores case, whitespace and typographic quotes, and quotes must be 8–30 words.

## When there is no guide
| Case | Status | Message |
|---|---|---|
| No passage scores 0.4 or more | `unsure` | « Je ne sais pas : aucune source fiable ne couvre ce cas. Voir l'équipe sécurité. » The writer isn't called |
| Every step was dropped | `unsure` | « Je ne sais pas : aucune étape n'a pu être sourcée. Voir l'équipe sécurité. » |
| A model is unavailable (error, timeout, 429, refusal, cut-off answer, missing key) | `unavailable` | « Guide indisponible : les modèles ne répondent pas. Sources trouvées ci-dessous. » The passages found are returned |

## « Pourquoi ? »
`POST /api/guides/{id}/why` re-ranks only the guide's own passages (using `PROMPT_REWRITE_QUESTION_V1`, which has no leg definitions), then answers with `PROMPT_WHY_V1`. It goes through the same quote check.

## Corpus (`backend/data/reference/`, pinned in `SOURCES.json`)
| Source | Units | Licence |
|---|---|---|
| ANSSI, *Recommandations de sécurité pour un système d'IA générative*, French and English | 35 + 35 | Licence Ouverte 2.0 |
| MITRE ATLAS 5.6.0, mitigations | 35 | Apache 2.0 |
| OWASP Top 10 for Agentic Applications (`owasp_asi.json`, typed by hand) | missing | CC BY-SA 4.0 |
| Runbooks (fictional, written by the team) | 6 | ours |

- **A changed file stops the build:** the build refuses any file whose hash doesn't match.
- **The app refuses an edited corpus:** it won't start if `corpus.json` doesn't match `corpus.sha256`.
- **Every loaded file must be pinned:** `owasp_asi.json` when present, and each runbook. An unpinned file stops the build, naming the file.

## Model cache (`cache.py`)
- **Coverage:** every model call goes through `Cached`.
- **Key:** the sha256 of the adapter and method, the model, the prompt version (a hash of the prompt text) and the input. The incident id is left out: the model never sees it, so a new incident with the same text replays.
- **Modes:**
  - `live`: call the model.
  - `record`: call and store.
  - `replay`: cache only, never the network.
  - `fallback`: call, and serve the stored answer if the model fails. This is the mode for the stage.
- **Recorded answers:** they're committed in `backend/data/cache/`, so re-record after changing a prompt, a model or the corpus.
- **Corpus vectors** (`embeddings.npy`, local only): rebuilt when the corpus, the embedding model or the row count changes.

## Model calls
- `store=False` on every OpenAI call: the provider keeps nothing (both OpenAI and Bedrock keep responses 30 days by default).
- Fail fast, so `fallback` reaches the cache quickly: OpenAI 20 s read, 5 s connect, 1 retry; Jev 5 s, 1 retry.
- A refusal or a cut-off structured answer counts as unavailable.
