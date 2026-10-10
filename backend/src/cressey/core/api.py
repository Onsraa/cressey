"""Runs and holds: register a run (Cressey issues its key), follow its steps, decide
holds."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from cressey.core.models import Hold, Run, RunCreated, RunIn
from cressey.core.runs import Runs

router = APIRouter()


def get_runs(request: Request) -> Runs:
    return request.app.state.runs


RunsDep = Annotated[Runs, Depends(get_runs)]


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
