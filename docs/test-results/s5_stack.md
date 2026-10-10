# S5: application stack (2026-10-08)

A throwaway blank project (backend plus web plus Docker) was built, checked and then deleted; only these results are kept.

## Versions that work together
- **Machine:**
  - Bun 1.4.0
  - Node 24.10.0
  - uv 0.12.2
  - Docker 29.6.2
- **Backend:**
  - Python 3.12
  - FastAPI 0.143.0
  - Pydantic 2.13.5
  - pydantic-settings 2.15.0
  - sse-starlette 3.5.0
  - uvicorn 0.54.0
  - openai 3.26.1
  - typesafe-sdk 0.7.2
  - fastmcp 4.0.11
- **Backend dev tools:**
  - ruff 0.16.10
  - ty 0.0.85
  - pytest 9.1.1
  - httpx (FastAPI's TestClient)
- **Web:**
  - Vite 8.3
  - React 19.2
  - **TypeScript 6.0.3**
  - Tailwind CSS 4.3.3 through `@tailwindcss/vite`
  - shadcn CLI 4.21.4 (radix, preset `nova`)
  - Biome 2.5.15
  - openapi-typescript 7.13.0
  - `@types/bun`

## Checks that passed
- **Backend** (a Pydantic model, a JSON endpoint, an SSE endpoint, settings read from `.env`):
  - `ruff check` and `ruff format`;
  - `ty check`;
  - `pytest`, 2 tests out of 2, including reading the SSE stream with `TestClient.stream`.
- **OpenAPI → TypeScript types:** `openapi-typescript openapi.json -o src/api.d.ts` took 13 ms, and the web code uses `components["schemas"]["Incident"]`. The backend's Pydantic models are the single source of truth.
- **Web:**
  - `biome check`;
  - `bun test` (1 test);
  - `tsc -b && vite build` (about 140 ms);
  - the dev server answers 200.
- **Single container:** a multi-stage Dockerfile, with Bun building the web and uv installing the backend. FastAPI serves the API and the built web (`StaticFiles(html=True)`).
  - The build takes 20 s once base images are cached, and the image is 378 MB.
  - `GET /` returns 200 and `GET /incidents` returns the JSON.

## Problems found, and their fixes
1. **TypeScript 7.0.2 breaks openapi-typescript.** The native TS 7 compiler doesn't expose the JavaScript API that the generator needs (`ts.factory` is undefined). TS 7 does compile the Vite app (`tsc -b` works). **Decision:** stay on TypeScript 6 (`typescript@6`), which is what the Vite template ships.
2. **create-vite** now sets up **oxlint** instead of ESLint. **Decision:** remove it and use Biome only.
3. **shadcn init asks interactive questions** unless it gets all its flags. The command that works without prompts:

   ```
   bunx shadcn@latest init --template vite --base radix --preset nova --yes --no-monorepo
   ```

   Preset names are `nova`, `vega`, `maia`, `lyra`, `mira`, `luma`, `sera` and `rhea`; `base-nova` is rejected. Components are added with `bunx shadcn@latest add button card badge progress --yes`. It needs the `@/*` path alias in both `tsconfig.json` and `tsconfig.app.json`, and in `vite.config.ts`.
4. **`bun:test` types are missing for `tsc`.** Fix: add `"bun"` to `compilerOptions.types` in `tsconfig.app.json`, with `@types/bun` installed.
5. **`uv sync` in Docker fails before the code is copied** ("Expected a Python module at src/…"). Fix: install the dependencies with `uv sync --frozen --no-dev --no-install-project` first, then copy the code.

## Not verified here
- **AWS deploy** (ECS Express Mode): needs the AWS CLI, which isn't installed, and account access.
- **ggshield in CI:** needs a GitGuardian API key.
- **Live model calls:** need keys.
