"""Play a recorded session through Cressey as the agent would: through the MCP gateway (its
calls run on Cressey's upstream) or through the Claude Code hook (each call announced, then
what the recording says it returned). The detection eval, the stage recorder, « Rejouer ×5 »
and the lab all play through here.

    uv run python -m cressey.replay.player data/sessions/demo-tests-impossibles.yaml --kind control
    uv run python -m cressey.replay.player ../lab/runs/<stamp>/transcript.jsonl \\
        --task "Reset the staging database so staging is healthy again." --pace 2.5 --typing 0.07
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

import httpx2
import mcp_types
import yaml
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, JsonValue, TypeAdapter

from cressey.adapters.claude_code import HOOK_PATH
from cressey.adapters.mcp import MCP_PATH
from cressey.domain.acts import Surface
from cressey.domain.runs import Mandate, RunKind
from cressey.engine.agent_text import PREFIX
from cressey.replay.importers import load_transcript
from cressey.replay.trajectory import Call, Say, Session, Trajectory
from cressey.settings import Settings

# How a call went for the agent: Cressey refused it, it failed, or it ran.
Outcome = Literal["refused", "failed", "done"]


class Played(BaseModel):
    session: str
    run_id: str
    kind: RunKind
    blocked_at: int | None  # the call Cressey refused, 1-based
    stopped_at: int | None = None  # the needed call that failed, 1-based
    report: str


class _Mcp:
    """An MCP client holding the run's key: its calls run on Cressey's upstream. Its words
    and its report go through the agent API."""

    def __init__(self, h: httpx2.AsyncClient, base_url: str, run_id: str, key: str):
        self.h, self.run_id = h, run_id
        self.auth = {"Authorization": f"Bearer {key}"}
        transport = StreamableHttpTransport(base_url + MCP_PATH, headers=self.auth)
        self.client = Client(transport)

    async def __aenter__(self) -> Self:
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        await self.client.__aexit__(kind, error, trace)

    async def say(self, text: str) -> None:
        path = f"/api/runs/{self.run_id}/messages"
        await self.h.post(path, json={"text": text}, headers=self.auth)

    async def call(self, step: Call, n: int) -> Outcome:
        result = await self.client.call_tool(step.call, step.args, raise_on_error=False)
        if not result.is_error:
            return "done"
        text = " ".join(
            c.text for c in result.content if isinstance(c, mcp_types.TextContent)
        )
        return "refused" if text.startswith(PREFIX) else "failed"

    async def end(self, report: str) -> None:
        path = f"/api/runs/{self.run_id}/report"
        await self.h.post(path, json={"text": report}, headers=self.auth)


class _Hook:
    """Claude Code's hook events, with the run's key: its words as they display, each call
    before it runs, then what the recording says it returned, and the end of the turn."""

    def __init__(self, h: httpx2.AsyncClient, key: str, typing: float):
        self.h, self.typing, self.said = h, typing, 0
        self.auth = {"Authorization": f"Bearer {key}"}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        return None

    async def _send(self, kind: str, **event: JsonValue) -> dict[str, JsonValue]:
        body = {"hook_event_name": kind, **event}
        sent = await self.h.post(HOOK_PATH, json=body, headers=self.auth)
        return sent.raise_for_status().json()

    async def say(self, text: str) -> None:
        """Whole, or three words at a time when typed out to be filmed."""
        self.said += 1
        words = text.split(" ")
        parts = range(0, len(words), 3) if self.typing else [0]
        chunks = [" ".join(words[i : i + 3]) for i in parts] if self.typing else [text]
        for i, chunk in enumerate(chunks):
            final = i == len(chunks) - 1
            delta = chunk if i == 0 else " " + chunk
            await self._send(
                "MessageDisplay", message_id=f"m{self.said}", delta=delta, final=final
            )
            await asyncio.sleep(self.typing)

    async def call(self, step: Call, n: int) -> Outcome:
        call: dict[str, JsonValue] = {
            "tool_name": step.call,
            "tool_input": step.args,
            "tool_use_id": f"c{n}",
        }
        answer = await self._send("PreToolUse", **call)
        decided = answer.get("hookSpecificOutput")
        if isinstance(decided, dict) and decided.get("permissionDecision") == "deny":
            return "refused"
        if step.returned is None:  # nothing recorded: Cressey never hears back
            return "done"
        if step.failed:
            await self._send("PostToolUseFailure", **call, error=step.returned)
            return "failed"
        await self._send("PostToolUse", **call, tool_response=step.returned)
        return "done"

    async def end(self, report: str) -> None:
        await self._send("Stop", last_assistant_message=report)


async def play(
    base_url: str,
    trajectory: Trajectory,
    kind: RunKind = "live",
    pace: float = 0.0,
    *,
    admin: str,
    surface: Surface = "mcp",
    typing: float = 0.0,
    transport: httpx2.AsyncBaseTransport | None = None,
    before_report: Callable[[str], Awaitable[None]] | None = None,
) -> Played:
    """Play `trajectory` through Cressey: register the run with the control plane's key
    (`admin`), then the agent's words and calls with the run's own key, then its report.
    `pace`: seconds after each call; `typing`: seconds between the words of a hook message;
    `transport`: an app in this process, for the hook (the MCP client goes over HTTP);
    `before_report`: awaited with the run's id before the report ends the run."""
    t = trajectory
    async with httpx2.AsyncClient(
        base_url=base_url, transport=transport, timeout=600
    ) as h:
        body = {
            "task": t.task,
            "mandate": t.mandate.model_dump(),
            "visibility": t.visibility,
            "kind": kind,
        }
        registered = await h.post(
            "/api/runs", json=body, headers={"Authorization": f"Bearer {admin}"}
        )
        run = registered.raise_for_status().json()
        agent = (
            _Mcp(h, base_url, run["id"], run["key"])
            if surface == "mcp"
            else _Hook(h, run["key"], typing)
        )
        blocked_at = stopped_at = None
        calls = 0
        async with agent:
            for step in t.steps:
                if step.say and t.visibility != "tools":
                    await agent.say(step.say)
                if isinstance(step, Say):
                    continue
                calls += 1
                outcome = await agent.call(step, calls)
                if outcome == "refused":
                    blocked_at = calls
                    break
                if outcome == "failed" and step.stop_if_error:
                    stopped_at = calls
                    break
                await asyncio.sleep(pace)
        stopped = blocked_at is not None or stopped_at is not None
        report = (t.report_if_blocked if stopped else None) or t.report
        if before_report is not None:
            await before_report(run["id"])
        await agent.end(report)
    return Played(
        session=t.id,
        run_id=run["id"],
        kind=kind,
        blocked_at=blocked_at,
        stopped_at=stopped_at,
        report=report,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Play a recorded session through Cressey.")
    p.add_argument(
        "source",
        type=Path,
        help="a scripted session (.yaml) or a Claude Code transcript (.jsonl)",
    )
    p.add_argument("--task", help="a transcript's task: it doesn't hold it")
    p.add_argument("--mandate", help="a transcript's mandate, as JSON")
    p.add_argument("--surface", choices=["mcp", "hook"], help="default: mcp, hook")
    p.add_argument("--kind", default="live", help="live, replay or control")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--pace", type=float, default=1.5, help="seconds after each call")
    p.add_argument(
        "--typing", type=float, default=0, help="seconds between a message's words"
    )
    a = p.parse_args()
    admin = Settings().admin_token
    if admin is None:
        p.error(
            "set CRESSEY_ADMIN_TOKEN in .env: registering a run needs the admin key"
        )
    transcript = a.source.suffix == ".jsonl"
    if transcript and not a.task:
        p.error("a transcript needs its task: --task")
    trajectory = (
        load_transcript(
            a.source,
            a.task,
            Mandate.model_validate_json(a.mandate) if a.mandate else None,
        )
        if transcript
        else Session.model_validate(yaml.safe_load(a.source.read_text()))
    )
    surface = TypeAdapter(Surface).validate_python(
        a.surface or ("hook" if transcript else "mcp")
    )
    kind = TypeAdapter(RunKind).validate_python(a.kind)
    played = play(
        a.url,
        trajectory,
        kind,
        a.pace,
        admin=admin.get_secret_value(),
        surface=surface,
        typing=a.typing,
    )
    print(asyncio.run(played).model_dump_json(indent=1))


if __name__ == "__main__":
    main()
