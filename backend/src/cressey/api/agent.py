"""What the agent itself sends, with its run key: its messages along the way, and its final
report, checked against the log."""

from fastapi import APIRouter, Request

from cressey.api.auth import AuthorizationHeader, RunsDep, own_run
from cressey.domain.runs import TextIn
from cressey.engine.report import report_check

router = APIRouter()


@router.post("/runs/{run_id}/messages", status_code=204)
async def message(
    run_id: str,
    body: TextIn,
    runs: RunsDep,
    authorization: AuthorizationHeader = "",
) -> None:
    """What the agent says along the way. Only the run's own key may send it."""
    runs.say(own_run(runs, run_id, authorization), body.text)


@router.post("/runs/{run_id}/report", status_code=204)
async def report(
    run_id: str,
    body: TextIn,
    request: Request,
    runs: RunsDep,
    authorization: AuthorizationHeader = "",
) -> None:
    """The agent's final report. It ends the run, and the decision model checks it against
    the log (S9). Only the run's own key may send it."""
    run = own_run(runs, run_id, authorization)
    runs.end(run, body.text)
    state = request.app.state
    runs.checked(run, await report_check(run, state.ledger, state.thresholds))
    state.engine.ended(run)
