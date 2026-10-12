"""Runs and holds: register a run (Cressey issues its key), follow its steps, decide
holds."""

import asyncio
import json
import secrets
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from cressey.core.hook import HOOK_PATH
from cressey.core.incidents import AssessTask, Incidents
from cressey.core.proxy import MCP_PATH
from cressey.domain.incidents import FleetSignal, Incident, Replay
from cressey.domain.owners import LegName
from cressey.domain.policy import Responses
from cressey.domain.runs import Hold, RejectIn, Run, RunCreated, RunIn, TextIn
from cressey.domain.status import EvalFile, LogHead, Status
from cressey.engine.agent_text import check_message, finish
from cressey.engine.report import report_check
from cressey.settings import DATA
from cressey.store.runs import Runs

# The human control plane: app.py puts all of it behind require_admin.
router = APIRouter()
# What the agent itself calls, with its run key.
agent_router = APIRouter()


def get_runs(request: Request) -> Runs:
    return request.app.state.runs


RunsDep = Annotated[Runs, Depends(get_runs)]


def get_incidents(request: Request) -> Incidents:
    return request.app.state.incidents


IncidentsDep = Annotated[Incidents, Depends(get_incidents)]


# The assessments in flight: the event loop keeps only weak references to its tasks.
_assessing: set[asyncio.Task[None]] = set()


async def _assess(run: Run, assess_task: AssessTask) -> None:
    run.preflight = await assess_task(run.task, run.mandate)


@router.post("/runs", status_code=201)
async def create_run(spec: RunIn, request: Request, runs: RunsDep) -> RunCreated:
    """The run starts at once; its task is assessed in the background (« Avant le run »)."""
    created = runs.create(spec)
    run = runs.get(created.id)
    assert run is not None
    if run.kind != "replay":  # « Rejouer ×5 » plays in throwaway instances
        assessing = _assess(run, request.app.state.assess_task)
        task = asyncio.get_running_loop().create_task(assessing)
        _assessing.add(task)
        task.add_done_callback(_assessing.discard)
    return created


@router.get("/runs")
async def list_runs(runs: RunsDep) -> list[Run]:
    return runs.all()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, runs: RunsDep) -> Run:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404)
    return run


def _own_run(runs: Runs, run_id: str, authorization: str) -> Run:
    """The run, when the request carries that run's own key."""
    run = runs.by_key(authorization.removeprefix("Bearer ").strip())
    if run is None or run.id != run_id:
        raise HTTPException(403)
    return run


AuthorizationHeader = Annotated[str, Header()]


def require_admin(request: Request, authorization: AuthorizationHeader = "") -> None:
    """The admin key, never a run key: an agent that reaches Cressey can't decide its own
    holds, unlock itself or switch a check to alert."""
    given = authorization.removeprefix("Bearer ").strip().encode()
    if not secrets.compare_digest(given, request.app.state.admin_token.encode()):
        raise HTTPException(
            401,
            "admin token required (CRESSEY_ADMIN_TOKEN)",
            headers={"WWW-Authenticate": "Bearer"},
        )


@agent_router.post("/runs/{run_id}/messages", status_code=204)
async def message(
    run_id: str,
    body: TextIn,
    runs: RunsDep,
    authorization: AuthorizationHeader = "",
) -> None:
    """What the agent says along the way. Only the run's own key may send it."""
    runs.say(_own_run(runs, run_id, authorization), body.text)


@agent_router.post("/runs/{run_id}/report", status_code=204)
async def report(
    run_id: str,
    body: TextIn,
    request: Request,
    runs: RunsDep,
    authorization: AuthorizationHeader = "",
) -> None:
    """The agent's final report. It ends the run, and the decision model checks it against
    the log (S9). Only the run's own key may send it."""
    run = _own_run(runs, run_id, authorization)
    runs.end(run, body.text)
    state = request.app.state
    runs.checked(run, await report_check(run, state.ledger, state.thresholds))


@router.get("/status")
async def status(request: Request, runs: RunsDep) -> Status:
    head, count = runs.log.head()
    return Status(
        mode="guard",
        model_mode=request.app.state.settings.model_mode,
        mcp_path=MCP_PATH,
        hook_path=HOOK_PATH,
        stop_after=request.app.state.policy.stuck.rejections,
        log=LogHead(hash=head, count=count, intact=runs.log.intact),
    )


@router.get("/incidents")
async def list_incidents(incidents: IncidentsDep) -> list[Incident]:
    """Most severe first, then the oldest."""
    return incidents.all()


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, incidents: IncidentsDep) -> Incident:
    incident = incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404)
    return incident


@router.get("/policy/responses")
async def get_responses(request: Request) -> Responses:
    """What Cressey does when each check fires: alert, review or stop."""
    return request.app.state.policy.responses


@router.put("/policy/responses")
async def set_responses(body: Responses, request: Request, runs: RunsDep) -> Responses:
    """Change it live. Every change is logged: alert means no call waits for a human."""
    request.app.state.policy.responses = body
    runs.log.append("responses", dict(body.model_dump()))
    return body


@router.get("/fleet")
async def fleet(incidents: IncidentsDep) -> list[FleetSignal]:
    """Runs held for the same target outside their mandate: a signal across runs."""
    return incidents.fleet()


@router.post("/incidents/{incident_id}/fixes/{leg}/approve", status_code=204)
async def approve_fix(incident_id: str, leg: LegName, incidents: IncidentsDep) -> None:
    """A human approves the fix Cressey proposed for one leg."""
    if not incidents.approve(incident_id, leg):
        raise HTTPException(404)


@router.post("/incidents/{incident_id}/replay")
async def replay_incident(incident_id: str, incidents: IncidentsDep) -> Replay:
    """« Rejouer ×5 » with the approved fixes: each session on a fresh Cressey."""
    replay = await incidents.replay(incident_id)
    if replay is None:
        raise HTTPException(404)
    return replay


SESSION_REPORTS: dict[str, Literal["detection", "ablation", "decision"]] = {
    "report-detection": "detection",
    "report-ablation": "ablation",
    "decision-model": "decision",
}


@router.get("/eval")
async def eval_reports() -> list[EvalFile]:
    """The eval reports in data/eval, for the Évaluation view."""
    files = []
    reports = sorted((DATA / "eval").glob("report-*.json"))
    for path in [*reports, DATA / "eval" / "decision-model.json"]:
        report = json.loads(path.read_text())
        kind = SESSION_REPORTS.get(path.stem, "guides")
        # The guide reports have no date field: their file's write time stands in.
        written = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        files.append(
            EvalFile(
                kind=kind,
                # The sessions are written by the team: a dev split.
                split=report["split"] if kind == "guides" else "dev",
                file=str(path.relative_to(DATA.parent)),
                date=report.get("date", written),
                report=report,
            )
        )
    return files


@router.post("/runs/{run_id}/unlock", status_code=204)
async def unlock(run_id: str, runs: RunsDep) -> None:
    """Give a stopped run its key back and reset the count of refused calls."""
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404)
    runs.unlock(run)


@router.get("/holds")
async def list_holds(runs: RunsDep) -> list[Hold]:
    return runs.holds()


# async on purpose: a decision resolves a future that lives on the server's event loop.
@router.post("/runs/{run_id}/steps/{n}/approve", status_code=204)
async def approve(run_id: str, n: int, runs: RunsDep) -> None:
    _decide(runs, run_id, n, approve=True)


@router.post("/runs/{run_id}/steps/{n}/reject", status_code=204)
async def reject(
    run_id: str,
    n: int,
    request: Request,
    runs: RunsDep,
    body: RejectIn | None = None,
) -> None:
    """Reject a held call, optionally with the reason the agent will read. The dashboard
    shows a checked draft, but the human may have edited it: it is checked again here."""
    message = body.message.strip() if body and body.message else ""
    if message:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(404, "no pending hold")
        message = finish(message)
        broken = check_message(message, run, request.app.state.policy.decoys)
        if broken:
            raise HTTPException(422, broken)
    _decide(runs, run_id, n, approve=False, message=message or None)


def _decide(
    runs: Runs, run_id: str, n: int, approve: bool, message: str | None = None
) -> None:
    if not runs.decide(run_id, n, approve, message):
        raise HTTPException(404, "no pending hold")
