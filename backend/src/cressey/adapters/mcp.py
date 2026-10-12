"""The MCP gateway agents point at: every tool call goes through the engine before it reaches
the real tool, and the tool gets the credential the key broker hands it, never the agent's."""

import json
import math

import mcp_types
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from cressey.adapters.broker import scoped
from cressey.engine.agent_text import UNKNOWN_KEY, note
from cressey.engine.decide import Engine, Refused

MCP_PATH = "/mcp"


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


def tool_text(result: ToolResult) -> str:
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


class Gateway(Middleware):
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        # A run is the key Cressey issued: session ids change on every call (S1).
        auth = get_http_headers(include={"authorization"}).get("authorization", "")
        engine, runs = self.engine, self.engine.runs
        run = runs.by_key(auth.removeprefix("Bearer ").strip())
        if run is None:
            raise ToolError(UNKNOWN_KEY)
        name, args = context.message.name, context.message.arguments or {}
        runs.route(run, "mcp")
        try:
            step = await engine.before(run, name, args)
        except Refused as refused:
            raise ToolError(str(refused)) from refused
        try:
            # The key broker: the tool gets the credential the mandate allows, never the agent's
            # own key. The Observer measures what happens without Cressey, so it's left alone.
            credential = (
                engine.policy.broker.get(name) if run.kind != "control" else None
            )
            if credential:
                sent = scoped(args, credential, run.mandate, step.status == "approved")
                message = context.message.model_copy(update={"arguments": dict(sent)})
                context = context.copy(message=message)
            result = await call_next(context)
            told = await engine.after(run, step, result.is_error, tool_text(result))
            # Added after the record: the ledger labels the tool's own text, not Cressey's.
            if told:
                result.content.append(mcp_types.TextContent(text=note(told)))
            return result
        finally:
            step.running = False  # its result is in, or the call failed


def build_mcp(engine: Engine, upstream: FastMCP) -> StarletteWithLifespan:
    proxy = create_proxy(upstream, name="cressey")
    proxy.add_middleware(Gateway(engine))
    return proxy.http_app(path=MCP_PATH)
