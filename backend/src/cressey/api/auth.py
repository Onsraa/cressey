"""Who may call what: the admin key for the control plane, a run's own key for what the
agent sends; and the app state a route reaches."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from cressey.adapters.auth import AuthorizationHeader, bearer
from cressey.domain.runs import Run
from cressey.incidents.incidents import Incidents
from cressey.store.runs import Runs


def get_runs(request: Request) -> Runs:
    return request.app.state.runs


RunsDep = Annotated[Runs, Depends(get_runs)]


def get_incidents(request: Request) -> Incidents:
    return request.app.state.incidents


IncidentsDep = Annotated[Incidents, Depends(get_incidents)]


def own_run(runs: Runs, run_id: str, authorization: str) -> Run:
    """The run, when the request carries that run's own key."""
    run = runs.by_key(bearer(authorization))
    if run is None or run.id != run_id:
        raise HTTPException(403)
    return run


def require_admin(request: Request, authorization: AuthorizationHeader = "") -> None:
    """The admin key, never a run key: an agent that reaches Cressey can't decide its own
    holds, unlock itself or switch a check to alert."""
    given = bearer(authorization).encode()
    if not secrets.compare_digest(given, request.app.state.admin_token.encode()):
        raise HTTPException(
            401,
            "admin token required (CRESSEY_ADMIN_TOKEN)",
            headers={"WWW-Authenticate": "Bearer"},
        )
