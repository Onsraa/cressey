"""One agent action, the same record whatever surface it came through (the MCP gateway, a
Claude Code hook; next, telemetry and a model gateway): who acted, through what, on which
model, and what it called. Who asked for it is read from its values by the engine."""

from typing import Literal

from pydantic import BaseModel, JsonValue

Surface = Literal["mcp", "hook"]
# Who asked for an act (the core design's I4): the task, the user's prompt, content the agent
# read in a tool's result, or the agent itself when none of its values came from elsewhere.
Asker = Literal["task", "user", "content", "agent"]


class Agent(BaseModel):
    """Who acts, as far as the surface says; None where it says nothing."""

    client: str | None = (
        None  # the program: MCP's client_info, "claude-code" for the hook
    )
    client_version: str | None = None
    model: str | None = None  # Claude Code's SessionStart and model switches name it
    sub_agent: str | None = (
        None  # Claude Code's agent_id, when a subagent made the call
    )
    sub_agent_type: str | None = None


class Act(BaseModel):
    surface: Surface
    agent: Agent
    tool: str
    args: dict[str, JsonValue]
