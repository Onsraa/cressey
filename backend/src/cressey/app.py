import secrets
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from cressey.adapters.claude_code import router as hook_router
from cressey.adapters.mcp import MCP_PATH, build_mcp
from cressey.api.agent import router as agent_router
from cressey.api.auth import require_admin
from cressey.api.control import router as control_router
from cressey.demo.agent import load_sessions
from cressey.demo.tools import demo_tools
from cressey.domain.guides import Guide, GuideIncident
from cressey.domain.policy import load_policy
from cressey.engine.agent_text import cached_drafter
from cressey.engine.decide import Engine
from cressey.engine.floor.tripwires import origin
from cressey.engine.preflight import assess_for
from cressey.guide.api import router as guide_router
from cressey.guide.api import write_guide
from cressey.guide.corpus import load_corpus
from cressey.incidents.incidents import Incidents
from cressey.judge import JevJudge, Judge
from cressey.replay.fixes import FixReplay
from cressey.settings import DATA, Settings
from cressey.store.eventlog import EventLog
from cressey.store.runs import Runs
from cressey.tasks import Tasks


def create_app(
    settings: Settings | None = None,
    make_guide: Callable[[GuideIncident], Guide] = write_guide,
    judge: Judge | None = None,
) -> FastAPI:
    s = settings or Settings()
    load_corpus(DATA / "corpus.json")  # refuse to start on an edited corpus
    state = s.state_dir
    if state is None:
        runs = Runs(EventLog())
    else:
        state.mkdir(parents=True, exist_ok=True)
        log = EventLog(state / "events.jsonl", state / "anchor.json")
        runs = Runs(log, state / "runs.jsonl")
    demo = s.demo_dir or Path(tempfile.mkdtemp(prefix="cressey-demo-"))

    def fresh(folder: Path) -> FastAPI:
        """A Cressey of its own for one replayed session; it shares a judge passed in. It
        keeps nothing: the replay is not part of this Cressey's record."""
        update = {"demo_dir": folder, "state_dir": None}
        return create_app(s.model_copy(update=update), make_guide, given)

    given = judge
    policy = load_policy(DATA / "policy.yaml")
    policy.decoys |= s.decoys
    judge = judge or JevJudge.from_settings(s)
    upstream = demo_tools(demo)
    # The task assessed before the run, against the tools as the agent sees them.
    assess_task = partial(assess_for, upstream, judge)
    incidents = Incidents(runs, make_guide, policy.fleet, assess_task)
    # On Bedrock the guide models sign with the AWS credentials: .env or boto3's own chain.
    guides = s.models == "bedrock" or s.openai_api_key is not None
    models_ready = guides and s.typesafe_api_key is not None
    drafter = cached_drafter(s) if models_ready else None
    engine = Engine(
        runs,
        incidents,
        policy,
        judge,
        s.hold_timeout,
        s.triangle_holds,
        s.holds,
        drafter,
        s.thought_holds,
        frozenset({origin(s.base_url), origin(s.dashboard_url)}),
    )
    mcp = build_mcp(engine, upstream)
    app = FastAPI(title="Cressey", lifespan=mcp.lifespan)
    app.state.runs, app.state.incidents, app.state.settings = runs, incidents, s
    app.state.judge, app.state.thresholds = judge, policy.triangle  # the report check
    app.state.policy = policy  # its responses change live
    app.state.engine = engine  # the Claude Code hook runs its decision
    app.state.ledger = engine.ledger  # the report check reads its labels
    app.state.assess_task = assess_task  # each new run's task
    app.state.assessing = Tasks()  # those assessments, in the background
    app.state.replay = FixReplay(
        incidents, runs, fresh, load_sessions
    )  # « Rejouer ×5 »
    # Unset, a random key per start: nobody outside knows it, the replays read it here.
    app.state.admin_token = (
        s.admin_token.get_secret_value() if s.admin_token else secrets.token_urlsafe(24)
    )
    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        models = "configured" if models_ready else "missing-keys"
        return {"status": "ok", "models": models}

    admin = [Depends(require_admin)]
    api.include_router(guide_router, dependencies=admin)
    api.include_router(control_router, dependencies=admin)
    api.include_router(agent_router)

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
