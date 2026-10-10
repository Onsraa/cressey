"""Runs and holds: register a run (Cressey issues its key), follow its steps, decide
holds."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from cressey.core.eventlog import verify
from cressey.core.incidents import Incidents
from cressey.core.models import (
    Hold,
    Incident,
    LogHead,
    ReportIn,
    Run,
    RunCreated,
    RunIn,
    Status,
)
from cressey.core.proxy import MCP_PATH
from cressey.core.runs import Runs

router = APIRouter()


def get_runs(request: Request) -> Runs:
    return request.app.state.runs


RunsDep = Annotated[Runs, Depends(get_runs)]


def get_incidents(request: Request) -> Incidents:
    return request.app.state.incidents


IncidentsDep = Annotated[Incidents, Depends(get_incidents)]


@router.post("/runs", status_code=201)
async def create_run(spec: RunIn, runs: RunsDep) -> RunCreated:
    return runs.create(spec)


@router.get("/runs")
async def list_runs(runs: RunsDep) -> list[Run]:
    return runs.all()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, runs: RunsDep) -> Run:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404)
    return run


@router.post("/runs/{run_id}/report", status_code=204)
async def report(
    run_id: str,
    body: ReportIn,
    runs: RunsDep,
    authorization: Annotated[str, Header()] = "",
) -> None:
    """The agent's final report. It ends the run; only the run's own key may send it."""
    run = runs.by_key(authorization.removeprefix("Bearer ").strip())
    if run is None or run.id != run_id:
        raise HTTPException(403)
    runs.end(run, body.text)


@router.get("/status")
async def status(request: Request, runs: RunsDep) -> Status:
    head, count = runs.log.head()
    return Status(
        mode="guard",
        model_mode=request.app.state.settings.model_mode,
        mcp_path=MCP_PATH,
        log=LogHead(hash=head, count=count, intact=verify(runs.log.events) is None),
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


@router.get("/holds")
async def list_holds(runs: RunsDep) -> list[Hold]:
    return runs.holds()


# async on purpose: a decision resolves a future that lives on the server's event loop.
@router.post("/runs/{run_id}/steps/{n}/approve", status_code=204)
async def approve(run_id: str, n: int, runs: RunsDep) -> None:
    _decide(runs, run_id, n, approve=True)


@router.post("/runs/{run_id}/steps/{n}/reject", status_code=204)
async def reject(run_id: str, n: int, runs: RunsDep) -> None:
    _decide(runs, run_id, n, approve=False)


def _decide(runs: Runs, run_id: str, n: int, approve: bool) -> None:
    if not runs.decide(run_id, n, approve):
        raise HTTPException(404, "no pending hold")
