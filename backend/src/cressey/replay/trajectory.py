"""One recorded session, whatever it was recorded from: what the agent said, each call it
made and, when it was recorded, what the call returned. The scripted sessions, a Claude Code
transcript and the lab's sources all become one (replay/importers.py), and one player plays
them (replay/player.py)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from cressey.domain.runs import Mandate, Visibility


class Say(BaseModel):
    """What the agent says with no call after it."""

    model_config = ConfigDict(extra="forbid")  # a step with a call is a Call

    say: str


class Call(BaseModel):
    say: str | None = None  # what the agent says before the call
    call: str
    args: dict[str, JsonValue] = {}
    # What it returned, when recorded: a hook replay sends it as the call's result. None: the
    # call runs on Cressey's upstream (an MCP replay of a scripted session).
    returned: str | None = None
    failed: bool = False
    stop_if_error: bool = (
        False  # the agent needs this call's result: it stops if it fails
    )


class Trajectory(BaseModel):
    id: str
    task: str
    mandate: Mandate = Field(default_factory=Mandate)
    visibility: Visibility = "messages"
    steps: list[Say | Call]
    report: str = "(no final message)"
    report_if_blocked: str | None = (
        None  # the report once Cressey stopped it, else `report`
    )


class Session(Trajectory):
    """A scripted session (data/sessions), with what Cressey should do with it: the detection
    eval scores it, « Rejouer ×5 » plays it again."""

    expect: Literal["held", "free"]
    variant_of: str | None = (
        None  # the incident session this one varies, for the replay
    )
    report_if_blocked: str
