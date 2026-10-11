"""The MCP proxy agents point at. Every tool call goes through Guard before it reaches
the real tool."""

import asyncio
import json
import logging
import math
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
from pydantic import JsonValue

from cressey.core.broker import scoped
from cressey.core.case import shadow_soon
from cressey.core.floor import check, trap
from cressey.core.incidents import Incidents
from cressey.core.judge import Judge
from cressey.core.models import Policy, Response, Run, Shadow, Step
from cressey.core.runs import Runs
from cressey.core.secret_scan import fingerprint, redact, scan
from cressey.core.triangle import (
    alarm,
    alarm_reason,
    label_soon,
    legs,
    read_after,
    read_before,
)

log = logging.getLogger(__name__)

WAY_OUT = "Declaring the task impossible is an accepted answer."
READ_ONLY = "read-only key: pressure and opportunity confirmed"
MCP_PATH = "/mcp"


def load_policy(path: Path) -> Policy:
    return Policy.model_validate(yaml.safe_load(path.read_text()))


def _size(b64: str) -> str:
    """The size of base64 data, without decoding it."""
    n = len(b64) * 3 // 4 - b64[-2:].count("=")
    return f"{math.ceil(n / 1024)} Ko"


def _mirrors(texts: list[str], structured: object) -> bool:
    """FastMCP returns a dict tool's result as JSON text too, and a str tool's as
    {"result": text}: that structured content is already read."""
    for text in texts:
        if structured == {"result": text}:
            return True
        try:
            if json.loads(text) == structured:
                return True
        except ValueError:  # not JSON: this text isn't a copy of it
            continue
    return False


def _text(result: ToolResult) -> str:
    """Everything the tool returned, as text the secret scan and the decision model read:
    text, embedded text resources and structured content, each once; a line for what isn't
    text, so it is never silently skipped."""
    lines: list[str] = []
    texts: list[str] = []
    for c in result.content:
        if isinstance(c, mcp_types.TextContent):
            texts.append(c.text)
            lines.append(c.text)
        elif isinstance(c, mcp_types.EmbeddedResource):
            res = c.resource
            if isinstance(res, mcp_types.TextResourceContents):
                lines.append(res.text)
            else:
                lines.append(f"[{res.mime_type or 'binaire'}, {_size(res.blob)}]")
        elif isinstance(c, mcp_types.ImageContent | mcp_types.AudioContent):
            lines.append(f"[{c.mime_type}, {_size(c.data)}]")
        elif isinstance(c, mcp_types.ResourceLink):
            lines.append(f"[lien : {c.uri}]")
    structured = result.structured_content
    if structured is not None and not _mirrors(texts, structured):
        lines.append(json.dumps(structured, ensure_ascii=False))
    return "\n".join(lines)


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
        # A run is the key Cressey issued: session ids change on every call (S1).
        auth = get_http_headers(include={"authorization"}).get("authorization", "")
        run = self.runs.by_key(auth.removeprefix("Bearer ").strip())
        if run is None:
            raise ToolError("Cressey: unknown key.")
        name, args = context.message.name, context.message.arguments or {}
        self.runs.route(run, "mcp")
        step = await self.before(run, name, args)
        try:
            # The key broker: the tool gets the credential the mandate allows, never the agent's
            # own key. The Observer measures what happens without Cressey, so it's left alone.
            credential = self.policy.broker.get(name) if run.kind != "control" else None
            if credential:
                sent = scoped(args, credential, run.mandate, step.status == "approved")
                message = context.message.model_copy(update={"arguments": dict(sent)})
                context = context.copy(message=message)
            result = await call_next(context)
            note = await self.after(run, step, result.is_error, _text(result))
            # Added after the record: the ledger labels the tool's own text, not Cressey's.
            if note:
                result.content.append(mcp_types.TextContent(text=f"Cressey: {note}"))
            return result
        finally:
            step.running = False  # its result is in, or the call failed

    async def before(self, run: Run, name: str, args: dict[str, JsonValue]) -> Step:
        """Cressey's decision on a call before it runs: its step, let through or approved.
        Raises ToolError when the call is refused, or held and not approved."""
        start = time.perf_counter()
        risk, floor = check(self.policy.tools.get(name), args, run.mandate)
        trapped = trap(args, self.policy.decoys)
        floor = trapped or floor
        # Off the event loop, like the result scan: a large argument takes a while to redact.
        # A copy of the secrets known so far, which other calls may add to meanwhile, and the
        # trap keys: one the agent got outside Cressey must not show in clear either.
        dumped = json.dumps(args, ensure_ascii=False)
        known = dict(run.known) | {
            v: fingerprint(v) for v in self.policy.decoys.values()
        }
        shown = await asyncio.to_thread(redact, dumped, known)
        step = self.runs.add_step(run, name, args, shown, risk, floor)
        try:
            if run.revoked:
                self.runs.mark(run, step, "denied")
                raise ToolError(f"Cressey: key suspended. {WAY_OUT}")
            triangle = await legs(run, step, self.judge, self.policy.triangle)
            if run.revoked:  # a parallel call was held while this one was being judged
                self.runs.mark(run, step, "denied")
                raise ToolError(f"Cressey: key suspended. {WAY_OUT}")
            triangle_hold = self.triangle_holds and alarm(triangle, risk)
            reason = floor or (alarm_reason(triangle) if triangle_hold else None)
            self.runs.score(run, step, triangle, reason)
            self._shadow_later(run, step, floor)
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
                raise ToolError(f"Cressey: action refused. {WAY_OUT}")
            # The agent learns it was held, never why: a reason teaches it what to route around
            # (Baker et al. 2025) and would name a trap key. The reason stays with the humans.
            held = ToolError(f"Cressey: action held. {WAY_OUT}")
            response = self._response(name, reason, bool(trapped), bool(floor))
            if response == "alert":
                self.runs.mark(run, step, "alerted")  # through, with its incident open
            elif reason and run.kind != "live":
                self.runs.mark(run, step, "would_hold")
                if run.kind == "replay":
                    raise held
            elif response == "stop":
                run.revoked = (
                    True  # as after a rejection: the rest of the run is denied
                )
                self.runs.mark(run, step, "denied")
                raise ToolError(f"Cressey: action refused. {WAY_OUT}")
            elif reason and not await self.runs.hold(run, step, self.hold_timeout):
                raise held
            return step
        except BaseException:
            step.running = False  # refused: no result will come
            raise

    def _shadow_later(self, run: Run, step: Step, floor: str | None) -> None:
        """What the case would decide for this call, beside today's decision and after it:
        in the background, never awaited, so the call's latency and hold are unchanged."""
        task = shadow_soon(run, step, floor, self.judge, self.policy.triangle)
        if task is not None:
            task.add_done_callback(lambda t: self._shadowed(run, step, t))

    def _shadowed(self, run: Run, step: Step, task: asyncio.Task[Shadow]) -> None:
        if task.cancelled():  # the server is stopping
            return
        failure = task.exception()
        if failure is not None:  # a background task has no caller to raise to
            log.error(
                "shadow of step %d of run %s failed", step.n, run.id, exc_info=failure
            )
            return
        self.runs.set_shadow(run, step, task.result())

    async def after(
        self, run: Run, step: Step, is_error: bool, text: str, label: bool = True
    ) -> str | None:
        """What the call returned, read: the secret scan, the ledger, and the triangle on a
        call too long to read before it ran. Without `label`, the caller reads the step
        later, once the agent's words are in. The way out, when this call carries it."""
        scanned = time.perf_counter()
        found = await asyncio.to_thread(scan, text)
        step.scan_ms = _ms_since(scanned)
        self.runs.record(run, step, is_error, text, found)
        if label:
            label_soon(
                run, step.n - 1, self.judge
            )  # read now: the next write won't wait for it
        # Too long to read before it ran: read now, without holding the developer's work.
        late = step.reason is None and step.risk != "read" and not read_before(step)
        if late and run.kind != "replay":
            task = asyncio.get_running_loop().create_task(self._read_late(run, step))
            self._late.add(task)
            task.add_done_callback(self._late.discard)
        return WAY_OUT if run.way_out_step == step.n else None

    async def _read_late(self, run: Run, step: Step) -> None:
        """A call that ran before it could be read: if the triangle would have held it,
        it alerts now, with its incident open."""
        try:
            late = await read_after(run, step, self.judge, self.policy.triangle)
        except Exception:  # a background task has no caller to raise to: report it
            log.exception("late read of step %d of run %s failed", step.n, run.id)
            return
        alarmed = self.triangle_holds and alarm(late, step.risk)
        reason = f"{alarm_reason(late)} (read afterwards)" if alarmed else None
        # Alarm or not, the step shows what the late read found, an unanswered model too.
        self.runs.score(run, step, late, reason)
        if not alarmed:
            return
        self.runs.mark(run, step, "alerted")
        self.incidents.open(run, step, "haute")


def build_mcp(guard: Guard, upstream: FastMCP) -> StarletteWithLifespan:
    proxy = create_proxy(upstream, name="cressey")
    proxy.add_middleware(guard)
    return proxy.http_app(path=MCP_PATH)
