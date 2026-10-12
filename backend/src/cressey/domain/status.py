"""What the control plane serves about Cressey itself: its modes, its log head, and the
measured reports."""

from typing import Literal

from pydantic import BaseModel, JsonValue


class LogHead(BaseModel):
    hash: str
    count: int
    intact: bool


class Status(BaseModel):
    mode: Literal["guard"]  # the only protection mode built so far
    model_mode: str
    mcp_path: str  # the MCP proxy agents point at
    hook_path: str  # the Claude Code hook agents post to
    stop_after: int  # rejected or expired holds in a turn that stop a run
    log: LogHead


class EvalFile(BaseModel):
    """A measured report, served as written, with where and when it was measured."""

    kind: Literal["guides", "detection", "ablation", "decision"]
    split: str  # dev, or held-out
    file: str
    date: str
    report: dict[str, JsonValue]
