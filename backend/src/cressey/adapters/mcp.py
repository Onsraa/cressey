"""The MCP gateway agents point at: every tool call goes through the engine before it reaches
the real tool, and the tool gets the credential the key broker hands it, never the agent's."""

import json
import math
from collections.abc import Sequence
from typing import Any

import mcp_types
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts.base import Prompt, PromptResult
from fastmcp.resources.base import Resource, ResourceResult
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp.shared.exceptions import MCPError
from mcp_types.jsonrpc import INVALID_REQUEST

from cressey.adapters.broker import scoped
from cressey.domain.acts import Act, Agent
from cressey.domain.runs import Run
from cressey.engine.agent_text import TOOLS_ONLY, UNKNOWN_KEY, note
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


def _client(context: MiddlewareContext[mcp_types.CallToolRequestParams]) -> Agent:
    """The MCP client, as it named itself in the handshake."""
    ctx = context.fastmcp_context
    params = ctx.session.client_params if ctx is not None else None
    if params is None:
        return Agent()
    return Agent(
        client=params.client_info.name, client_version=params.client_info.version
    )


# Before a client can name its run: the handshake.
HANDSHAKE = ("initialize", "ping", "server/discover")


class Gateway(Middleware):
    """The upstreams' tools, each call decided by the engine. Nothing else passes: no
    request without a run's key, and no resource or prompt, which would be acts Cressey
    neither decides nor records."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _run(self) -> Run | None:
        # A run is the key Cressey issued: session ids change on every call (S1).
        auth = get_http_headers(include={"authorization"}).get("authorization", "")
        return self.engine.runs.by_key(auth.removeprefix("Bearer ").strip())

    async def on_request(
        self,
        context: MiddlewareContext[mcp_types.Request[Any, Any]],
        call_next: CallNext[mcp_types.Request[Any, Any], Any],
    ) -> Any:
        # A tool call checks its key itself, to tell the agent why it is refused.
        open_ = context.method in HANDSHAKE or context.method == "tools/call"
        if not open_ and self._run() is None:
            raise MCPError(INVALID_REQUEST, UNKNOWN_KEY)
        return await call_next(context)

    async def on_list_resources(
        self,
        context: MiddlewareContext[mcp_types.ListResourcesRequest],
        call_next: CallNext[mcp_types.ListResourcesRequest, Sequence[Resource]],
    ) -> Sequence[Resource]:
        return []

    async def on_list_resource_templates(
        self,
        context: MiddlewareContext[mcp_types.ListResourceTemplatesRequest],
        call_next: CallNext[
            mcp_types.ListResourceTemplatesRequest, Sequence[ResourceTemplate]
        ],
    ) -> Sequence[ResourceTemplate]:
        return []

    async def on_list_prompts(
        self,
        context: MiddlewareContext[mcp_types.ListPromptsRequest],
        call_next: CallNext[mcp_types.ListPromptsRequest, Sequence[Prompt]],
    ) -> Sequence[Prompt]:
        return []

    async def on_read_resource(
        self,
        context: MiddlewareContext[mcp_types.ReadResourceRequestParams],
        call_next: CallNext[mcp_types.ReadResourceRequestParams, ResourceResult],
    ) -> ResourceResult:
        raise MCPError(INVALID_REQUEST, TOOLS_ONLY)

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mcp_types.GetPromptRequestParams],
        call_next: CallNext[mcp_types.GetPromptRequestParams, PromptResult],
    ) -> PromptResult:
        raise MCPError(INVALID_REQUEST, TOOLS_ONLY)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        engine, runs = self.engine, self.engine.runs
        run = self._run()
        if run is None:
            raise ToolError(UNKNOWN_KEY)
        name, args = context.message.name, context.message.arguments or {}
        runs.route(run, "mcp")
        agent = _client(context)
        agent.model = run.agent.model
        act = Act(surface="mcp", agent=agent, tool=name, args=dict(args))
        try:
            step = await engine.before(run, act)
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
