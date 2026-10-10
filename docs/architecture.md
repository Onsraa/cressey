# Architecture

## Components
| Component | Path | Status |
|---|---|---|
| App factory, settings, health, SPA fallback | `backend/src/cressey/app.py`, `settings.py` | built |
| Guide pipeline: corpus, retrieval, adapters, pipeline, store, API, eval, cache | `backend/src/cressey/guide/` | built |
| Core loop, piece 1: MCP proxy, safety floor, hold and revoke, runs API | `backend/src/cressey/core/` (`proxy.py`, `floor.py`, `runs.py`, `api.py`), `backend/data/policy.yaml` | built |
| Core loop, building blocks: source tracing, hash-chained event log | `core/trace.py`, `core/eventlog.py` | built, not wired in yet |
| Core loop, piece 2: secret scan, event log, triangle scoring with Jev on a run summary | `core/secret_scan.py`, `core/eventlog.py`, `core/triangle.py`, `core/judge.py` | built |
| Core loop, piece 3: incidents with source tracing, guides per owner written in the background | `core/incidents.py` | built |
| Core loop, next: fixes and « Rejouer ×5 », the agent's messages, the full-run review on hold, the eval endpoint | — | to build |
| Demo tools (synthetic): a workspace holding a fake production key, a SQLite database of 5 fake users | `backend/src/cressey/demo/tools.py` | built |
| Demo agent: a scripted replay of synthetic sessions, played through Cressey | `backend/src/cressey/demo/agent.py`, `backend/data/sessions/` (format in `sessions.md`) | built |
| Dashboard | `web/src/` | skeleton only |

## Request flow (target)
```
agent ──MCP──▶ Cressey proxy (fastmcp, on_call_tool) ──▶ real tools
                │ hash-chained event log
                ▼
        detection: safety floor + triangle over the run state (code decides; Jev labels from a run summary)
                │ on hold: an LLM reads the whole run and labels the legs (never releases the hold)
                │ GuideIncident
                ▼
        guide pipeline ──▶ /api/guides ──▶ dashboard (types generated from OpenAPI)
```

## Backend
- **Python 3.12, uv.** Package `cressey` under `backend/src/`.
- **FastAPI.** Every API route is under `/api`. The last `/api` route is a catch-all 404, so API typos never reach the SPA.
- **SPA fallback.** If `CRESSEY_WEB_DIR/index.html` exists, `/assets` is served as static files and any other path returns `index.html`. Paths that resolve outside the web folder are never served.
- **Settings** (`pydantic-settings`, read from `../.env` then `.env`):

| Field | Env var | Default |
|---|---|---|
| `openai_api_key` | `OPENAI_API_KEY` | none. An empty value counts as missing |
| `openai_base_url` | `OPENAI_BASE_URL` | none (OpenAI). For Bedrock: `https://bedrock-runtime.<region>.amazonaws.com/openai/v1`, with a Bedrock API key in `OPENAI_API_KEY` |
| `typesafe_api_key` | `TYPESAFE_API_KEY` | none. An empty value counts as missing |
| `web_dir` | `CRESSEY_WEB_DIR` | `web` |
| `model_mode` | `CRESSEY_MODEL_MODE` | `live` (`live`, `record`, `replay` or `fallback`) |
| `cache_dir` | `CRESSEY_CACHE_DIR` | `data/cache` |
| `rewrite_model` | — | `gpt-5.4-mini` |
| `writer_model` | — | `gpt-5.5` |
| `embedding_model` | — | `text-embedding-3-small` |
| `relevance_min` | — | `0.4` |
| `hold_timeout` | `CRESSEY_HOLD_TIMEOUT` | `240` s. Under the MCP client's 300 s default, so the agent gets Cressey's answer |
| `demo_dir` | `CRESSEY_DEMO_DIR` | a new temp folder at each start |

## API
| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/health` | — | `{"status":"ok","models":"configured"|"missing-keys"}` |
| POST | `/api/guides` | `GuideIncident` | 201 `Guide`, including when status is `unavailable` |
| GET | `/api/guides/{id}` | — | 200 `Guide`, or 404 |
| POST | `/api/guides/{id}/why` | `{"question": str}`, 3–500 characters | 200 `WhyAnswer`, 404 or 422 |
| POST | `/api/runs` | `{"task": str, "mandate": {"may_destroy": [tables], "may_send_to": [addresses or "@domain"], "may_read_secrets": [names]}, "visibility": "tools"\|"messages"\|"reasoning", "kind": "live"\|"replay"\|"control"}` | 201 `{"id", "key"}`. The key is shown once; Cressey keeps only its hash |
| GET | `/api/runs` | — | 200 runs with their steps |
| GET | `/api/runs/{id}` | — | 200 `Run`, or 404 |
| GET | `/api/holds` | — | 200 calls waiting for a human |
| POST | `/api/runs/{id}/steps/{n}/approve` | — | 204, or 404 when that step isn't held |
| POST | `/api/runs/{id}/steps/{n}/reject` | — | 204, or 404 |
| POST | `/api/runs/{id}/messages` | `{"text": str}`, with `Authorization: Bearer <run key>` | 204. Agent text, secrets redacted. 403 with another key |
| POST | `/api/runs/{id}/report` | `{"text": str}`, with `Authorization: Bearer <run key>` | 204: the run ends. 403 with another key |
| GET | `/api/incidents` | — | 200 incidents, « critique » first, then the oldest |
| GET | `/api/incidents/{id}` | — | 200 `Incident`, or 404 |
| GET | `/api/status` | — | 200 `{"mode": "guard", "model_mode", "mcp_path", "log": {"hash", "count", "intact"}}` |
| any | `/mcp` | MCP over streamable HTTP, `Authorization: Bearer <run key>` | the proxied tools |

Types are in `backend/src/cressey/guide/models.py`. The web app uses the generated `web/src/api/schema.d.ts`.

## Core loop, piece 1
- **Check:** each call is classified with the policy (`backend/data/policy.yaml`: `read`, `write`, `destructive`, `sql`, `egress`) and checked against the run's mandate (`core/floor.py`).
- **Held when:**
  - the tool is missing from the policy, or is `destructive`;
  - the SQL is destructive and touches a table outside `may_destroy`, or can't be classified;
  - a recipient is outside `may_send_to`.
- **While a call is held,** the run's key is revoked: its other calls are denied.
  - Approval runs the call once and reinstates the key.
  - Rejection or expiry answers « Cressey : action retenue (…). Déclarer la tâche impossible est une réponse acceptée. » The key stays revoked.
- **Run kinds:** `live` holds and waits for a human. `control` (« Observateur ») is logged and never held. `replay` never waits: a call that would be held is blocked and marked `would_hold`, and that replay fails.
- **Records:** every call becomes a step with its risk class, status, `held_until` and `decided_at`, and two timings: `check_ms` (Cressey's decision, before the tool runs) and `scan_ms` (the secret scan of the result).
  - What the agent read, and the raw arguments, are kept in memory for tracing and never served.
  - Each result is scanned for secrets (`core/secret_scan.py`, first 16 KB, off the event loop). The step lists them by name and fingerprint. From then on their values are replaced by `[secret:<fingerprint>]` in served arguments and in the report.
- **Triangle** (`core/triangle.py`, thresholds in `policy.yaml` under `triangle`), computed on every call from the run so far:
  - **Pressure** is confirmed by 2 failed calls or 2 repeated identical calls. A deadline word in the task raises the score but doesn't confirm it.
  - **Opportunity** is confirmed by a secret read that the mandate's `may_read_secrets` doesn't list.
  - **Rationalization** uses Jev, asked « Is this action needed for the task? » (the S2 wording) on a run summary built by code with secrets redacted. Drift = (1 − needed) × risk weight (read 0, write 0.5, destructive 1). It's confirmed at 0.5 or more. Reads don't call Jev. When Jev is unavailable, the leg stays unconfirmed and says so.
  - **Two confirmed legs** hold any call that isn't a read, with the reason « triangle : … confirmées ». Each step keeps the three legs (score, confirmed, facts).
  - Jev's answers go through the same cache modes as the guide models (`data/cache/judge/`).
- **Incidents** (`core/incidents.py`): every held call in a `live` or `control` run opens one. Replays open none.
  - **Severity:** « critique » when the safety floor held the call, « haute » when only the triangle did.
  - **Sources:** each value of the call is traced to the first step that read it (`core/trace.py`), with how it matched. A secret shows by name only.
  - **Guides:** one per confirmed leg, for its owner. Pressure goes to the task author, opportunity to the key owner, rationalization to the platform owner. A floor hit with no confirmed leg goes to the SOC.
    - They start in the background as soon as the call is held. Each owner's status reads `pending`, then the guide's status and id.
    - Each summary is one root-cause sentence built by code from the facts, with secrets redacted.
  - **Decision:** the incident shows the held call's current status (`approved` stays visible).
- **Event log:** every run, call, status change, result and report is appended to the hash-chained log (`core/eventlog.py`). `GET /api/status` serves its head and whether the chain verifies.
- **State:** runs, holds and the log live in memory for the life of the process.

## Web
- **Stack:** Vite 8, React 19, TypeScript 6, Tailwind v4, shadcn (radix, preset nova), Biome.
- **API client:** `web/src/api/client.ts` exposes `apiGet` and `apiPost`, which throw `ApiError(status, body)`.
- **Types:** `bun run gen:api` regenerates them from `backend/openapi.json`. CI fails if they're stale.

## Run
| Command | What it does |
|---|---|
| `./dev.sh` | Backend on :8000 and Vite on :5173, which proxies `/api` |
| `docker compose up --build` | One image, web and API on :8000. `.env` is optional |
| `cd backend && uv run python -m cressey.guide.corpus build` | Rebuilds `data/corpus.json` |
| `cd backend && uv run python -m cressey.guide.eval --split dev` | Writes `data/eval/report-dev.json` |
| `cd backend && uv run python -m cressey.demo.evaluate` | Plays every session on a fresh Cressey and writes `data/eval/report-detection.json` |
| `cd backend && uv run python -m cressey.demo.agent data/sessions/demo-tests-impossibles.yaml --kind live` | Plays the demo session through the running server (`--kind control` for the control run) |

## CI (`.github/workflows/ci.yml`)
- **backend:** ruff, ruff format, ty, pytest, then the OpenAPI export.
- **web:** regenerates the types and fails if they changed, then Biome, tsc, `bun test` and the build.
- **secrets:** ggshield. It needs the `GITGUARDIAN_API_KEY` repo secret, and warns when the key is missing.

## Deployment
- **Target: AWS** (the Bedrock partnership covers hosting and models).
- **Not built yet:** the container deploy and the Bedrock adapters.
- **Where Bedrock plugs in:** the adapters in `clients.py`.
  - Bedrock exposes an OpenAI-compatible endpoint at `https://bedrock-runtime.<region>.amazonaws.com/openai/v1`.
  - Claude models are reached through the Anthropic Messages API on that endpoint.
  - Whether Claude also answers through Chat Completions there is not verified.
- **Checked on 2026-10-10 in the AWS docs:**
  - `bedrock-runtime` serves the OpenAI Responses API. The OpenAI SDK works by setting `OPENAI_BASE_URL` and a Bedrock API key; the writer and rewriter code stays.
  - OpenAI models on Bedrock: GPT-5.6 Sol, Terra and Luna (`global.openai.gpt-5.6-sol`, …). gpt-5.5 and gpt-5.4-mini were not found, so the models change and the eval is re-run.
  - No OpenAI embedding model was found. Candidate: Cohere Embed Multilingual v3 (French), called through boto3.
  - Not verified: structured output (`text_format`) through Bedrock. Needs one call with a Bedrock key.
