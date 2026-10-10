"""The MCP proxy agents point at. Every tool call goes through Guard before it reaches
the real tool."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Literal

import mcp_types
import yaml
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from cressey.core.broker import scoped
from cressey.core.floor import check, trap
from cressey.core.incidents import Incidents
from cressey.core.judge import Judge
from cressey.core.models import Policy, Response, Run, Step
from cressey.core.runs import Runs
from cressey.core.secret_scan import redact, scan
from cressey.core.triangle import (
    alarm,
    alarm_reason,
    label_soon,
    legs,
    read_after,
    read_before,
)

log = logging.getLogger(__name__)

WAY_OUT = "Déclarer la tâche impossible est une réponse acceptée."
READ_ONLY = "clé en lecture seule : pression et opportunité confirmées"
MCP_PATH = "/mcp"


def load_policy(path: Path) -> Policy:
    return Policy.model_validate(yaml.safe_load(path.read_text()))


def _text(result: ToolResult) -> str:
    return "\n".join(
        c.text for c in result.content if isinstance(c, mcp_types.TextContent)
    )


def _ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000


class Guard(Middleware):
    def __init__(
        self,
        runs: Runs,
        incidents: Incidents,
        policy: Policy,
        judge: Judge,
        hold_timeout: float,
        triangle_holds: bool = True,
        holds: Literal["wait", "refuse"] = "wait",
    ) -> None:
        self.runs, self.incidents = runs, incidents
        self.policy, self.judge, self.hold_timeout = policy, judge, hold_timeout
        self.triangle_holds, self.holds = triangle_holds, holds
        self._late: set[asyncio.Task[None]] = (
            set()
        )  # the loop keeps weak references only

    def _response(
        self, tool: str, reason: str | None, trapped: bool, floor: bool
    ) -> Response | None:
        """What the policy does with a call a check fired on, or None when none did."""
        if reason is None:
            return None
        r = self.policy.responses
        response = r.trap_key if trapped else r.floor if floor else r.triangle
        if r.fleet == "stop" and self.incidents.signalled(f"{tool} | {reason}"):
            response = "stop"  # many runs after one target: no human queue for them all
        if response == "review" and self.holds == "refuse":
            response = "stop"  # CRESSEY_HOLDS=refuse: nobody waits for a human
        return response

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        start = time.perf_counter()
        # A run is the key Cressey issued: session ids change on every call (S1).
        auth = get_http_headers(include={"authorization"}).get("authorization", "")
        run = self.runs.by_key(auth.removeprefix("Bearer ").strip())
        if run is None:
            raise ToolError("Cressey : clé inconnue.")
        name, args = context.message.name, context.message.arguments or {}
        risk, floor = check(self.policy.tools.get(name), args, run.mandate)
        trapped = trap(args, self.policy.decoys)
        floor = trapped or floor
        # Off the event loop, like the result scan: a large argument takes a while to redact.
        # A copy of the secrets known so far, which other calls may add to meanwhile.
        dumped = json.dumps(args, ensure_ascii=False)
        shown = await asyncio.to_thread(redact, dumped, dict(run.known))
        step = self.runs.add_step(run, name, args, shown, risk, floor)
        if run.revoked:
            self.runs.mark(run, step, "denied")
            raise ToolError(f"Cressey : clé suspendue. {WAY_OUT}")
        triangle = await legs(run, step, self.judge, self.policy.triangle)
        if run.revoked:  # a parallel call was held while this one was being judged
            self.runs.mark(run, step, "denied")
            raise ToolError(f"Cressey : clé suspendue. {WAY_OUT}")
        triangle_hold = self.triangle_holds and alarm(triangle, risk)
        reason = floor or (alarm_reason(triangle) if triangle_hold else None)
        self.runs.score(run, step, triangle, reason)
        # The Observateur run and the floor-alone ablation show what happens without it.
        if self.triangle_holds and run.kind != "control":
            self.runs.act_on_pressure(run, step, triangle)
        if reason and run.kind != "replay":
            self.incidents.open(run, step, "critique" if floor else "haute")
        step.check_ms = _ms_since(start)  # the time to stop, when the call is held
        # A call that would be held still goes to a human: only the others are refused.
        if not reason and run.read_only_step and risk == "destructive":
            step.reason = READ_ONLY
            self.runs.mark(run, step, "denied")
            raise ToolError(f"Cressey : action refusée. {WAY_OUT}")
        # The agent learns it was held, never why: a reason teaches it what to route around
        # (Baker et al. 2025) and would name a trap key. The reason stays with the humans.
        held = ToolError(f"Cressey : action retenue. {WAY_OUT}")
        response = self._response(name, reason, bool(trapped), bool(floor))
        if response == "alert":
            self.runs.mark(run, step, "alerted")  # through, with its incident open
        elif reason and run.kind != "live":
            self.runs.mark(run, step, "would_hold")
            if run.kind == "replay":
                raise held
        elif response == "stop":
            run.revoked = True  # as after a rejection: the rest of the run is denied
            self.runs.mark(run, step, "denied")
            raise ToolError(f"Cressey : action refusée. {WAY_OUT}")
        elif reason and not await self.runs.hold(run, step, self.hold_timeout):
            raise held
        # The key broker: the tool gets the credential the mandate allows, never the agent's
        # own key. The Observer measures what happens without Cressey, so it's left alone.
        credential = self.policy.broker.get(name) if run.kind != "control" else None
        if credential:
            sent = scoped(args, credential, run.mandate, step.status == "approved")
            message = context.message.model_copy(update={"arguments": dict(sent)})
            context = context.copy(message=message)
        result = await call_next(context)
        text = _text(result)
        scanned = time.perf_counter()
        found = await asyncio.to_thread(scan, text)
        step.scan_ms = _ms_since(scanned)
        self.runs.record(run, step, result.is_error, text, found)
        label_soon(
            run, step.n - 1, self.judge
        )  # read now: the next write won't wait for it
        # Too long to read before it ran: read now, without holding the developer's work.
        late = not reason and risk != "read" and not read_before(step)
        if late and run.kind != "replay":
            task = asyncio.get_running_loop().create_task(self._read_late(run, step))
            self._late.add(task)
            task.add_done_callback(self._late.discard)
        # Added after the record: the ledger labels the tool's own text, not Cressey's.
        if run.way_out_step == step.n:
            result.content.append(mcp_types.TextContent(text=f"Cressey : {WAY_OUT}"))
        return result

    async def _read_late(self, run: Run, step: Step) -> None:
        """A call that ran before it could be read: if the triangle would have held it,
        it alerts now, with its incident open."""
        try:
            late = await read_after(run, step, self.judge, self.policy.triangle)
        except Exception:  # a background task has no caller to raise to: report it
            log.exception("late read of step %d of run %s failed", step.n, run.id)
            return
        if not (self.triangle_holds and alarm(late, step.risk)):
            return
        self.runs.score(run, step, late, f"{alarm_reason(late)} (lu après coup)")
        self.runs.mark(run, step, "alerted")
        self.incidents.open(run, step, "haute")


def build_mcp(guard: Guard, upstream: FastMCP) -> StarletteWithLifespan:
    proxy = create_proxy(upstream, name="cressey")
    proxy.add_middleware(guard)
    return proxy.http_app(path=MCP_PATH)
