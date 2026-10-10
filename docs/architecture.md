# Architecture

## Components
| Component | Path | Status |
|---|---|---|
| App factory, settings, health, SPA fallback | `backend/src/cressey/app.py`, `settings.py` | built |
| Guide pipeline: corpus, retrieval, adapters, pipeline, store, API, eval, cache | `backend/src/cressey/guide/` | built |
| Core loop: MCP proxy, mandate and safety floor, triangle scoring, hold, revoke, trace, incidents | — | to build (design in `concept.md`) |
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
| `typesafe_api_key` | `TYPESAFE_API_KEY` | none. An empty value counts as missing |
| `web_dir` | `CRESSEY_WEB_DIR` | `web` |
| `model_mode` | `CRESSEY_MODEL_MODE` | `live` (`live`, `record`, `replay` or `fallback`) |
| `cache_dir` | `CRESSEY_CACHE_DIR` | `data/cache` |
| `rewrite_model` | — | `gpt-5.4-mini` |
| `writer_model` | — | `gpt-5.5` |
| `embedding_model` | — | `text-embedding-3-small` |
| `relevance_min` | — | `0.4` |

## API
| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/health` | — | `{"status":"ok","models":"configured"|"missing-keys"}` |
| POST | `/api/guides` | `GuideIncident` | 201 `Guide`, including when status is `unavailable` |
| GET | `/api/guides/{id}` | — | 200 `Guide`, or 404 |
| POST | `/api/guides/{id}/why` | `{"question": str}`, 3–500 characters | 200 `WhyAnswer`, 404 or 422 |

Types are in `backend/src/cressey/guide/models.py`. The web app uses the generated `web/src/api/schema.d.ts`.

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
