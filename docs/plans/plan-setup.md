# Cressey project setup: implementation plan (part 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax. Do the tasks **in order**. Each one ends with a check. If a task gets stuck, write down which step it was and go on to the next task that doesn't depend on it.

**Goal:** a repo that runs on Saturday at 11:45, with:
- a backend and a web app wired together;
- API types generated from the backend;
- one command to start the development servers;
- tests, lint and type checks;
- a single Docker image;
- CI that also checks there are no secrets.

**Architecture:**
- `backend/` is a uv project with the `cressey` package, built on FastAPI. Every API route is under `/api`.
- `web/` is a Bun project using Vite, React and TypeScript.
- In development, Vite forwards `/api` to FastAPI on port 8000.
- In production, FastAPI serves the built web from `/` and the API from `/api`, in one container.

**Tech stack:** every version comes from `../spikes/results/s5_stack.md`.
- Python 3.12, uv 0.12.2;
- FastAPI 0.143.0, Pydantic 2.13.5, pydantic-settings 2.15.0, uvicorn 0.54.0, sse-starlette 3.5.0;
- ruff 0.16.10, ty 0.0.85, pytest 9.1.1;
- Bun 1.4.0, Vite 8, React 19, TypeScript 6;
- Tailwind CSS 4.3.3, shadcn CLI 4.21.4, Biome 2.5.15, openapi-typescript 7.13.0;
- Docker 29.6.2.

**Spec:** `concept.md` (Deployment section), `../spikes/results/s5_stack.md` (five pitfalls and their fixes) and `../spikes/results/s6_s7.md` (the `uv --package` layout, `Settings(_env_file=None)`, the SPA fallback and path traversal, all verified). Part 1 (`plan-guide-rag.md`) adds its own dependencies in its Task 1.

## Global constraints
- **When:** the repo is created on Saturday after 11:30. Nothing is committed before then.
- **Commits:** no AI co-author trailers.
- **Versions:**
  - **TypeScript 6**, not 7: TS 7 breaks openapi-typescript.
  - **Biome only:** remove the oxlint that the Vite template installs.
- **Secrets:** `.env` is git-ignored. `.env.example` lists the variable names with no values: `OPENAI_API_KEY`, `TYPESAFE_API_KEY`.
- **Routes:** every API route starts with `/api`. The SPA owns `/`.
- **Ports:** backend 8000, Vite dev server 5173.

## Review focus
1. **Someone clones the repo with no `.env`.** The backend must still start, and `/api/health` returns `{"status":"ok","models":"missing-keys"}` instead of crashing. Test in Task 2.
2. **A deep link in production** (for example `/guides/abc`) must return the SPA, not a 404. Test in Task 6.
3. **The API changed but the types weren't regenerated.** CI regenerates them and fails if the file differs. Check in Task 7.
4. **A secret is committed by mistake.** The ggshield job fails. Check in Task 7.
5. **Docker is built without the web.** The image build fails before it finishes, not at run time. Check in Task 6.

---

### Task 1: Repo skeleton
**Files:** create `README.md`, `.gitignore`, `.env.example`.
- [ ] **Step 1:** Run `git init cressey && cd cressey`.
- [ ] **Step 2:** Create `.gitignore` with these lines: `.env`, `.venv/`, `__pycache__/`, `node_modules/`, `web/dist/`, `backend/openapi.json`, `backend/data/embeddings.npy`, `*.sqlite`.
- [ ] **Step 3:** Create `.env.example` with `OPENAI_API_KEY=` and `TYPESAFE_API_KEY=`. Copy your real `.env` in next to it.
- [ ] **Check:** `git check-ignore .env` prints `.env`.
- [ ] **Commit:** `chore: repo skeleton`.

### Task 2: Backend project
**Files:**
- Create: `backend/` (from `uv init`), `backend/src/cressey/app.py`, `backend/src/cressey/settings.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- **Produces:**
  - `create_app(settings: Settings | None = None) -> FastAPI`, with an `/api` prefix router and `GET /api/health`. The router's **last** route is `GET /api/{rest:path}`, which raises 404, so the SPA fallback never answers an API typo (S7). Tests pass `Settings(_env_file=None, ...)` so that the developer's real `.env` never leaks into them.
  - `Settings` (pydantic-settings). Its keys are `SecretStr | None`, read from `../.env` and `.env`. It also has `web_dir: Path = Field(Path("web"), validation_alias="CRESSEY_WEB_DIR")`, the built web folder (`/app/web` in Docker). Part 1 extends this class.
  - Its config is `SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", populate_by_name=True)`, so that tests can pass `web_dir=…`. Verified on 2026-10-09 with pydantic-settings 2.15.0. The quirk: with `populate_by_name`, the unprefixed `WEB_DIR` is also read from the environment. It's harmless; don't set it.

- [ ] **Step 1:** Run `uv init --package --python 3.12 --name cressey backend`. This produces `backend/src/cressey/`.
- [ ] **Step 2:** Run `cd backend && uv add fastapi uvicorn sse-starlette pydantic pydantic-settings && uv add --dev ruff ty pytest httpx2`. FastAPI's `TestClient` warns that `httpx` is deprecated (S7)..
- [ ] **Step 3:** In `pyproject.toml`, add the pytest settings:
  - `[tool.pytest.ini_options]` with `addopts = "-m 'not live'"`;
  - `markers = ["live: calls real APIs"]`;
  - `testpaths = ["tests"]`.
- [ ] **Step 4: Write the failing tests**

```python
def test_health_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False); monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    r = TestClient(create_app(Settings(_env_file=None))).get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "models": "missing-keys"}

def test_health_with_keys():
    s = Settings(_env_file=None, openai_api_key="x", typesafe_api_key="y")
    assert TestClient(create_app(s)).get("/api/health").json()["models"] == "configured"
```

- [ ] **Step 5:** Implement `create_app()` and `Settings`. If `web/dist` exists, mount it at `/` (see Task 6).
- [ ] **Check:** `uv run pytest -q` shows 2 passed, and `uv run ruff check && uv run ruff format --check && uv run ty check` passes.
- [ ] **Commit:** `feat(backend): app factory, settings, health`.

### Task 3: Web project
**Files:** create `web/` (from create-vite), then modify `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.app.json`, `web/package.json`.
- [ ] **Step 1:** From the repo root:
  - run `bunx create-vite@latest web --template react-ts --no-interactive && cd web && bun install`;
  - then `bun remove oxlint` and delete `.oxlintrc.json`.
- [ ] **Step 2:** Run `bun add -d typescript@6 @types/bun @types/node @biomejs/biome openapi-typescript && bun add tailwindcss @tailwindcss/vite`.
- [ ] **Step 3:** In `vite.config.ts`, add:
  - `tailwindcss()` to the plugins;
  - the alias `@` → `./src`, via `fileURLToPath(new URL("./src", import.meta.url))`;
  - `server.proxy = {"/api": "http://localhost:8000"}`.

  Put `@import "tailwindcss";` in `src/index.css`.
- [ ] **Step 4:** In **both** `tsconfig.json` and `tsconfig.app.json`, add `"paths": {"@/*": ["./src/*"]}`. In `tsconfig.app.json`, set `"types": ["bun", "vite/client"]`.
- [ ] **Step 5:** Run `bunx shadcn@latest init --template vite --base radix --preset nova --yes --no-monorepo`, then `bunx shadcn@latest add button card badge progress --yes`. Add other components later, the same way.
- [ ] **Step 6:** Run `bunx biome init`, then set the `package.json` scripts to these values:

```json
"dev": "vite", "build": "tsc -b && vite build", "test": "bun test",
"check": "biome check .", "ci": "biome ci . && tsc -b && bun test",
"gen:api": "openapi-typescript ../backend/openapi.json -o src/api/schema.d.ts"
```

- [ ] **Check:**
  - `bun run build` ends with `✓ built in …`;
  - `bun run check` passes;
  - `bun test` passes (add one trivial test so the test runner has something to run).
- [ ] **Commit:** `feat(web): Vite React TS6 + Tailwind v4 + shadcn + Biome`.

### Task 4: Typed API contract
**Files:**
- Create: `backend/src/cressey/export_openapi.py`, `web/src/api/client.ts`
- Test: `web/src/api/client.test.ts`

**Interfaces:**
- **Produces:**
  - `uv run python -m cressey.export_openapi`, which writes `backend/openapi.json` from `create_app().openapi()`.
  - `web/src/api/schema.d.ts`, generated.
  - `apiGet<T>(path: string): Promise<T>` and `apiPost<T>(path: string, body: unknown): Promise<T>`. Both throw `ApiError(status, body)` when the response isn't OK.

- [ ] **Step 1:** Write the failing test. Use `globalThis.fetch = mock(...)` from `bun:test`.
  - A 404 response makes `apiGet` reject with `ApiError` and `status === 404`.
  - A 200 response resolves with the parsed JSON.
- [ ] **Step 2:** Implement `client.ts`, using `fetch("/api" + path)` and JSON parsing. Implement `export_openapi.py` (a few lines).
- [ ] **Check:** `cd backend && uv run python -m cressey.export_openapi && cd ../web && bun run gen:api && bun test` writes `schema.d.ts`, and the tests pass.
- [ ] **Commit:** `feat: OpenAPI export, generated TS types, fetch client`.

### Task 5: One command for the dev loop
**Files:** create `dev.sh` at the repo root, and make it executable.
- [ ] **Step 1:** `dev.sh` starts `cd backend && uv run uvicorn cressey.app:create_app --factory --reload --port 8000` and `cd web && bun run dev` in parallel. It uses `trap 'kill 0' EXIT` so that Ctrl-C stops both.
- [ ] **Check:** with `./dev.sh` running, `curl -s localhost:5173/api/health` returns the health JSON through the Vite proxy, and `curl -s -o /dev/null -w "%{http_code}" localhost:5173/` returns `200`.
- [ ] **Commit:** `chore: dev.sh runs backend and web together`.

### Task 6: Single Docker image and compose
**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`
- Modify: `backend/src/cressey/app.py` (SPA fallback)

- [ ] **Step 1: The Dockerfile.** This is the version verified in S5, with the uv fix:
  1. Stage `web` (`oven/bun:1.4`): `bun install --frozen-lockfile`, then `bun run build`.
  2. Stage `app` (`python:3.12-slim`, with `uv` copied in from `ghcr.io/astral-sh/uv:0.12`):
     - copy `backend/pyproject.toml` and `backend/uv.lock`;
     - run `uv sync --frozen --no-dev --no-install-project`;
     - copy `backend/`;
     - run `uv sync --frozen --no-dev` to install the package;
     - copy `/web/dist` from the web stage to `./web`;
     - `CMD ["uv","run","--no-dev","uvicorn","cressey.app:create_app","--factory","--host","0.0.0.0","--port","8000"]`.

  The `.dockerignore` excludes `web/node_modules`, `web/dist`, `backend/.venv` and `.env`.
- [ ] **Step 2: SPA fallback.** In `create_app()`, when `settings.web_dir / "index.html"` exists:
  - mount `StaticFiles(directory=web_dir / "assets")` at `/assets`;
  - then add a catch-all route `GET /{path:path}`, registered **after** the `/api` router. If `(web_dir / path).resolve()` is a file **inside** `web_dir.resolve()` (use `is_relative_to`), serve it with `FileResponse`. Otherwise serve `index.html`.

  Don't mount StaticFiles at `/`: it would answer 404 for deep links before the fallback runs. Paths that start with `api/` never reach the fallback. Add these tests:

```python
def test_spa_deep_link_returns_index(tmp_path):
    (tmp_path / "index.html").write_text("<div id=\"root\"></div>"); (tmp_path / "assets").mkdir()
    r = TestClient(create_app(Settings(_env_file=None, web_dir=tmp_path))).get("/guides/abc")
    assert r.status_code == 200 and 'id="root"' in r.text

def test_fallback_never_serves_files_outside_web_dir(tmp_path):
    web = tmp_path / "web"; web.mkdir(); (web / "assets").mkdir(); (web / "index.html").write_text("index")
    (tmp_path / "secret.txt").write_text("nope")
    r = TestClient(create_app(Settings(_env_file=None, web_dir=web))).get("/..%2Fsecret.txt")
    assert "nope" not in r.text

def test_unknown_api_route_is_404_not_index(tmp_path):
    (tmp_path / "index.html").write_text("index"); (tmp_path / "assets").mkdir()
    assert TestClient(create_app(Settings(_env_file=None, web_dir=tmp_path))).get("/api/nope").status_code == 404
```

- [ ] **Step 3:** `compose.yaml` defines one service, `cressey`, with `build: .`, `env_file: .env` and `ports: ["8000:8000"]`.
- [ ] **Check:**
  - `docker compose up --build -d` builds in about 20 s once the base images are cached;
  - `curl -s localhost:8000/api/health` returns the health JSON;
  - `curl -s -o /dev/null -w "%{http_code}" localhost:8000/guides/abc` returns `200`;
  - finish with `docker compose down`.
- [ ] **Commit:** `feat: single-image Docker build with SPA fallback`.

### Task 7: CI
**Files:** create `.github/workflows/ci.yml`.

The workflow has three jobs, triggered on push and pull request:
- **backend:** set up uv (`astral-sh/setup-uv`), then in `backend/`:
  - `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, `uv run pytest -q`;
  - then `uv run python -m cressey.export_openapi`.
- **web:** set up Bun (`oven-sh/setup-bun`), download the `openapi.json` produced by the backend job as an artifact, then:
  - `bun install --frozen-lockfile`;
  - `bun run gen:api`;
  - `git diff --exit-code src/api/schema.d.ts`, which fails if the committed types are out of date;
  - `bun run ci`, then `bun run build`.
- **secrets** (verified in S8 from the action's README):
  - `actions/checkout` with `fetch-depth: 0`, then `uses: GitGuardian/ggshield-action@v1` (latest tag v1.55.0).
  - Environment: `GITHUB_PUSH_BEFORE_SHA: ${{ github.event.before }}`, `GITHUB_PUSH_BASE_SHA: ${{ github.event.base }}`, `GITHUB_DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}`, `GITGUARDIAN_API_KEY: ${{ secrets.GITGUARDIAN_API_KEY }}`.
  - Create the `GITGUARDIAN_API_KEY` repo secret on Saturday. Without a key, run `ggshield secret scan repo .` locally before the deadline instead.

- [ ] **Check:** the first push shows all three jobs green. Commit a fake secret on a throwaway branch, and the secrets job must turn red. Delete the branch afterwards.
- [ ] **Commit:** `ci: lint, types, tests, generated types drift, secret scan`.

---

## Done when
- [ ] Tasks 1–7 are checked off, and `./dev.sh` plus `docker compose up` both work on the demo laptop.
- [ ] Part 1 (`plan-guide-rag.md`) can start: its Task 1 adds its dependencies to `backend/`.
- [ ] Each dashboard page then fits into `web/src/` one piece at a time, using `apiGet`/`apiPost` and the shadcn components.
