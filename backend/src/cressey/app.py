import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from cressey.core.api import router as core_router
from cressey.core.eventlog import EventLog
from cressey.core.hook import router as hook_router
from cressey.core.incidents import Incidents
from cressey.core.judge import JevJudge, Judge
from cressey.core.preflight import assess_for
from cressey.core.proxy import MCP_PATH, Guard, build_mcp, load_policy
from cressey.core.runs import Runs
from cressey.demo.agent import load_sessions
from cressey.demo.replay import replay
from cressey.demo.tools import demo_tools
from cressey.guide.api import router as guide_router
from cressey.guide.api import write_guide
from cressey.guide.cache import wrap_drafter
from cressey.guide.corpus import DATA, load_corpus
from cressey.guide.models import Guide, GuideIncident
from cressey.settings import Settings


def create_app(
    settings: Settings | None = None,
    make_guide: Callable[[GuideIncident], Guide] = write_guide,
    judge: Judge | None = None,
) -> FastAPI:
    s = settings or Settings()
    load_corpus(DATA / "corpus.json")  # refuse to start on an edited corpus
    runs = Runs(EventLog())
    demo = s.demo_dir or Path(tempfile.mkdtemp(prefix="cressey-demo-"))

    def fresh(folder: Path) -> FastAPI:
        """A Cressey of its own for one replayed session; it shares a judge passed in."""
        return create_app(s.model_copy(update={"demo_dir": folder}), make_guide, given)

    given = judge
    policy = load_policy(DATA / "policy.yaml")
    policy.decoys |= s.decoys
    judge = judge or JevJudge.from_settings(s)
    upstream = demo_tools(demo)
    # The task assessed before the run, against the tools as the agent sees them.
    assess_task = partial(assess_for, upstream, judge)
    incidents = Incidents(
        runs,
        make_guide,
        lambda fixes, task: replay(fresh, fixes, task, load_sessions()),
        policy.fleet,
        assess_task,
    )
    # On Bedrock the guide models sign with the AWS credentials: .env or boto3's own chain.
    guides = s.models == "bedrock" or s.openai_api_key is not None
    models_ready = guides and s.typesafe_api_key is not None
    drafter = wrap_drafter(s) if models_ready else None
    guard = Guard(
        runs,
        incidents,
        policy,
        judge,
        s.hold_timeout,
        s.triangle_holds,
        s.holds,
        drafter,
    )
    mcp = build_mcp(guard, upstream)
    app = FastAPI(title="Cressey", lifespan=mcp.lifespan)
    app.state.runs, app.state.incidents, app.state.settings = runs, incidents, s
    app.state.judge, app.state.thresholds = judge, policy.triangle  # the report check
    app.state.policy = policy  # its responses change live
    app.state.guard = guard  # the Claude Code hook runs its decision
    app.state.assess_task = assess_task  # each new run's task
    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        models = "configured" if models_ready else "missing-keys"
        return {"status": "ok", "models": models}

    api.include_router(guide_router)
    api.include_router(core_router)

    # Must stay the last /api route: keeps API typos from falling through to the SPA.
    @api.get("", include_in_schema=False)
    @api.get("/{rest:path}", include_in_schema=False)
    def api_not_found(rest: str = "") -> None:
        raise HTTPException(404)

    app.include_router(api)
    app.include_router(hook_router)  # the agents' second way in, beside MCP_PATH
    # The URL agents put in their MCP config. Registered before the SPA fallback.
    app.router.routes.append(Route(MCP_PATH, endpoint=mcp))
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
