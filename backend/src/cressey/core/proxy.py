"""The MCP proxy agents point at. Every tool call goes through Guard before it reaches
the real tool."""

from pathlib import Path

import mcp_types
import yaml
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from cressey.core.floor import check
from cressey.core.models import Policy
from cressey.core.runs import Runs

WAY_OUT = "Déclarer la tâche impossible est une réponse acceptée."


def load_policy(path: Path) -> Policy:
    return Policy.model_validate(yaml.safe_load(path.read_text()))


def _text(result: ToolResult) -> str:
    return "\n".join(
        c.text for c in result.content if isinstance(c, mcp_types.TextContent)
    )


class Guard(Middleware):
    def __init__(self, runs: Runs, policy: Policy, hold_timeout: float) -> None:
        self.runs, self.policy, self.hold_timeout = runs, policy, hold_timeout

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        # A run is the key Cressey issued: session ids change on every call (S1).
        auth = get_http_headers(include={"authorization"}).get("authorization", "")
        run = self.runs.by_key(auth.removeprefix("Bearer ").strip())
        if run is None:
            raise ToolError("Cressey : clé inconnue.")
        name, args = context.message.name, context.message.arguments or {}
        risk, reason = check(self.policy.tools.get(name), args, run.mandate)
        step = self.runs.add_step(run, name, args, risk)
        step.reason = reason
        if run.revoked:
            step.status = "denied"
            raise ToolError(f"Cressey : clé suspendue. {WAY_OUT}")
        if reason and not await self.runs.hold(run, step, self.hold_timeout):
            raise ToolError(f"Cressey : action retenue ({reason}). {WAY_OUT}")
        result = await call_next(context)
        step.is_error, step.result = result.is_error, _text(result)
        return result


def build_mcp(
    runs: Runs, policy: Policy, upstream: FastMCP, hold_timeout: float
) -> StarletteWithLifespan:
    proxy = create_proxy(upstream, name="cressey")
    proxy.add_middleware(Guard(runs, policy, hold_timeout))
    return proxy.http_app(path="/mcp")
