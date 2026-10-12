"""The demo agent: a scripted replay of a synthetic session, played through Cressey like a
real agent (an MCP client holding the run's key).

    uv run python -m cressey.demo.agent data/sessions/demo-tests-impossibles.yaml --kind control
"""

import argparse
import asyncio
from pathlib import Path
from typing import Literal

import httpx2
import mcp_types
import yaml
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, Field, JsonValue, TypeAdapter

from cressey.adapters.mcp import MCP_PATH
from cressey.domain.runs import Mandate, RunKind, Visibility
from cressey.engine.agent_text import PREFIX
from cressey.settings import DATA, Settings

SESSIONS = DATA / "sessions"


class Call(BaseModel):
    say: str | None = None  # what the agent says before the call
    call: str
    args: dict[str, JsonValue] = {}
    stop_if_error: bool = (
        False  # the agent needs this call's result: it stops if it fails
    )


class Session(BaseModel):
    id: str
    expect: Literal["held", "free"]  # should Cressey hold this session?
    variant_of: str | None = (
        None  # the incident session this one varies, for the replay
    )
    task: str
    mandate: Mandate = Field(default_factory=Mandate)
    visibility: Visibility = "messages"
    steps: list[Call]
    report: str
    report_if_blocked: str


class Played(BaseModel):
    session: str
    run_id: str
    kind: RunKind
    blocked_at: int | None  # the call Cressey refused, 1-based
    stopped_at: int | None = None  # the needed call that failed, 1-based
    report: str


def load_sessions(folder: Path = SESSIONS) -> list[Session]:
    return [
        Session.model_validate(yaml.safe_load(p.read_text()))
        for p in sorted(folder.glob("*.yaml"))
    ]


def _text(result: CallToolResult) -> str:
    return " ".join(
        c.text for c in result.content if isinstance(c, mcp_types.TextContent)
    )


async def play(
    base_url: str,
    session: Session,
    kind: RunKind = "live",
    pace: float = 0.0,
    *,
    admin: str,
) -> Played:
    """Play `session` through Cressey: register the run with the control plane's key
    (`admin`), make the calls with the run's own key, report."""
    async with httpx2.AsyncClient(base_url=base_url) as h:
        body = {
            "task": session.task,
            "mandate": session.mandate.model_dump(),
            "visibility": session.visibility,
            "kind": kind,
        }
        registered = await h.post(
            "/api/runs", json=body, headers={"Authorization": f"Bearer {admin}"}
        )
        run = registered.raise_for_status().json()
        auth = {"Authorization": f"Bearer {run['key']}"}
        blocked_at = stopped_at = None
        transport = StreamableHttpTransport(base_url + MCP_PATH, headers=auth)
        async with Client(transport) as agent:
            for n, step in enumerate(session.steps, start=1):
                if step.say and session.visibility != "tools":
                    said = {"text": step.say}
                    await h.post(
                        f"/api/runs/{run['id']}/messages", json=said, headers=auth
                    )
                result = await agent.call_tool(
                    step.call, step.args, raise_on_error=False
                )
                if result.is_error and _text(result).startswith(PREFIX):
                    blocked_at = n
                    break
                if result.is_error and step.stop_if_error:
                    stopped_at = n
                    break
                await asyncio.sleep(pace)
        stopped = blocked_at is not None or stopped_at is not None
        report = session.report_if_blocked if stopped else session.report
        await h.post(
            f"/api/runs/{run['id']}/report", json={"text": report}, headers=auth
        )
    return Played(
        session=session.id,
        run_id=run["id"],
        kind=kind,
        blocked_at=blocked_at,
        stopped_at=stopped_at,
        report=report,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Play a synthetic session through Cressey.")
    p.add_argument("session", type=Path)
    p.add_argument("--kind", default="live", help="live, replay or control")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--pace", type=float, default=1.5, help="seconds between calls")
    a = p.parse_args()
    admin = Settings().admin_token
    if admin is None:
        p.error(
            "set CRESSEY_ADMIN_TOKEN in .env: registering a run needs the admin key"
        )
    session = Session.model_validate(yaml.safe_load(a.session.read_text()))
    kind = TypeAdapter(RunKind).validate_python(a.kind)
    played = play(a.url, session, kind, a.pace, admin=admin.get_secret_value())
    print(asyncio.run(played).model_dump_json(indent=1))


if __name__ == "__main__":
    main()
