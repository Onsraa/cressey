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
1. **Rewrite** (gpt-5.4-mini, or GPT-5.6 Sol on Bedrock; `PROMPT_REWRITE_INCIDENT_V1`): the incident becomes one French query and one English query. The prompt defines the triangle's three legs.
2. **Search** (`retrieve.py`): three queries (French, English, raw text), each through BM25 and through embeddings, which makes 6 ranked lists. They're merged by reciprocal rank fusion (`k = 60`), keeping the top 8. The embeddings come from text-embedding-3-small, or from Cohere Embed Multilingual v3 on Bedrock, which embeds the corpus as passages (`search_document`) and each query as a query (`search_query`). If a query embedding fails, that search continues with BM25 only; the next search tries embeddings again.
3. **Re-rank** (Jev `jev-1.13.0`): one yes/no question per passage (« The passage directly answers the question »). Passages scoring under **0.4** are discarded.
   - **Rerank 3.5 on Bedrock** (`CRESSEY_RERANKER=bedrock`): one call scores every passage, threshold 0.2. Measured weaker on 10-10 (6/8 guides against 8/8), like Strands Decider (3/8): see `evaluation.md`.
   - **Each re-ranker has its own threshold,** set on the dev set with `--calibrate` (the S6 method: expected passages kept against others kept, and no out-of-scope question kept). The model name is part of the cache key, so a switch needs a new recording.
4. **Write** (gpt-5.5, on OpenAI or on Bedrock; `PROMPT_GUIDE_V1`): at most 4 steps. Each cites one passage id and a verbatim quote of 8–20 words. The incident text sits between `<incident>` tags and is treated as data, never as instructions. `<`, `>` and `&` in it are escaped, so it can't close the tag.
5. **Check, in code:** a step is kept only if its `source_id` is among the passages given to the writer and its quote appears in that passage. Matching ignores case, whitespace and typographic quotes, and quotes must be 8–30 words.

## When there is no guide
| Case | Status | Message |
|---|---|---|
| No passage reaches the threshold (0.4 with Jev) | `unsure` | « Je ne sais pas : aucune source fiable ne couvre ce cas. Voir l'équipe sécurité. » The writer isn't called |
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
- **Key:** the sha256 of the adapter and method, the model, the prompt version (a hash of the prompt text) and the input. The incident id is left out: the model never sees it, so a new incident with the same text replays. An embedding's input says whether it's a query, so a query never gets the answer recorded for the same text as a passage.
- **Modes:**
  - `live`: call the model.
  - `record`: call and store.
  - `replay`: cache only, never the network.
  - `fallback`: call, and serve the stored answer if the model fails. This is the mode for the stage.
- **Recorded answers:** they're committed in `backend/data/cache/`, so re-record after changing a prompt, a model or the corpus.
- **Corpus vectors** (`embeddings.npy`, local only): rebuilt when the corpus, the embedding model or the row count changes. Switching `CRESSEY_MODELS` re-embeds the corpus once and overwrites the file.

## Model calls
- **Providers** (`CRESSEY_MODELS`): `bedrock` by default (10-10). It sends the rewrite and the writing to the Responses API of `bedrock-runtime`, each request signed with SigV4 from the AWS credentials, and the embeddings to Cohere Embed through boto3. Same prompts, same structured output (`evaluation.md`, « Bedrock models »).
- `store=False` on every Responses call, OpenAI or Bedrock: the provider keeps nothing (both keep responses 30 days by default).
- Fail fast, so `fallback` reaches the cache quickly: OpenAI and Bedrock 20 s read, 5 s connect, 1 retry; Jev 5 s, 1 retry.
- A refusal or a cut-off structured answer counts as unavailable.
