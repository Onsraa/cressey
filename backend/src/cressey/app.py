from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cressey.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    app = FastAPI(title="Cressey")
    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        ok = s.openai_api_key is not None and s.typesafe_api_key is not None
        return {"status": "ok", "models": "configured" if ok else "missing-keys"}

    # Must stay the last /api route: keeps API typos from falling through to the SPA.
    @api.get("", include_in_schema=False)
    @api.get("/{rest:path}", include_in_schema=False)
    def api_not_found(rest: str = "") -> None:
        raise HTTPException(404)

    app.include_router(api)
    _mount_web(app, s)
    return app


def _mount_web(app: FastAPI, s: Settings) -> None:
    web = s.web_dir.resolve()
    if not (web / "index.html").exists():
        return
    if (web / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = (web / path).resolve()
        if path and f.is_file() and f.is_relative_to(web):
            return FileResponse(f)
        return FileResponse(web / "index.html")
