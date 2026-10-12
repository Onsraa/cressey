"""The policy Cressey enforces, from three kinds of file: the engine's settings (policy.yaml:
the floor's thresholds, the responses, the triangle's thresholds, the fleet signal, when a run
stops), what each surface's own tools do (catalogs/), and the deployment's profile (profiles/:
the MCP servers it fronts, what their tools do, the key broker and the trap keys)."""

from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import BaseModel, Field, JsonValue

from cressey.domain.acts import Surface
from cressey.domain.runs import Indicator

# What Cressey does with a call a check fired on: let it through with an incident, hold it
# for a human, or refuse it at once.
Response = Literal["alert", "review", "stop"]


def _thought_floors() -> dict[str, float]:
    """Every indicator, and what a thought is about, at 0.5; R at 0.2."""
    floors = dict.fromkeys([*get_args(Indicator), "about"], 0.5)
    floors["R"] = 0.2
    return floors


class ToolRule(BaseModel):
    # An edit changes the workspace file at the path its `arg` holds; a write's `arg`, if
    # any, is no path.
    kind: Literal["read", "write", "edit", "destructive", "sql", "egress", "shell"]
    arg: str | None = (
        None  # the argument holding the SQL, the recipients, the path or the command
    )


class Thresholds(BaseModel):
    """When observed facts confirm a leg (policy.yaml, `triangle`)."""

    failures: int = 2  # failed calls that confirm pressure
    repeats: int = 2  # identical calls repeated that confirm pressure
    judgment: float = 0.5  # S9: the judgment on a write that confirms rationalization
    report: float = 0.8  # S9: the score at which the final report is flagged
    evidence: int = (
        8  # flagged parts of earlier steps the judgment sees, any distance back
    )
    deadline_words: list[str] = []
    # S9: the floor a thought's probability must reach for each indicator to be kept.
    thoughts: dict[str, float] = Field(default_factory=_thought_floors)


class Fleet(BaseModel):
    """When runs held for the same target outside their mandate become a signal across runs
    (policy.yaml, `fleet`)."""

    runs: int = 3  # distinct runs held for that target
    window_minutes: int = 15


class Stuck(BaseModel):
    """When a run stops (policy.yaml, `stuck`)."""

    rejections: int = 3  # rejected or expired holds in one turn that suspend the key


class Credential(BaseModel):
    """The key broker's credentials for one tool argument; Cressey picks one per call."""

    arg: str  # the argument that carries the key
    read: str  # reads only: the resource refuses any change made with it
    write: str  # for a mandate that grants changes, or a call a human approved


class Responses(BaseModel):
    """What Cressey does when each check fires (policy.yaml, `responses`), changeable live.
    Alert lets the call through and opens an incident; the key broker still hands it only
    what the mandate grants. The report check only ever alerts: the run is over."""

    floor: Response = (
        "review"  # destructive outside the mandate, protected or frozen path
    )
    trap_key: Response = "review"
    trap_key_read: Response = "alert"  # a decoy key in a call that only reads
    irreversible: Response = "review"  # Jev: a write that can't be undone
    # Jev: a write that changes production; off: not held for that alone.
    production: Response | Literal["off"] = "review"
    triangle: Response = "review"  # the judgment, with pressure or opportunity
    fleet: Literal["alert", "stop"] = (
        "alert"  # stop: once the signal is up, refuse its target
    )


class Floor(BaseModel):
    """What Jev labels for the safety floor (policy.yaml, `floor`). Its labels only add holds:
    none lifts a hold code made."""

    read: float = 0.95  # a tool missing from `tools` is a read from this probability
    irreversible: float = 0.5  # a write is held from this probability
    production: float = 0.7  # a write changes production from this probability


class Policy(BaseModel):
    tools: dict[Surface, dict[str, ToolRule]]  # by surface: one name can be two tools
    floor: Floor = Field(default_factory=Floor)
    responses: Responses = Field(default_factory=Responses)
    triangle: Thresholds = Field(default_factory=Thresholds)
    fleet: Fleet = Field(default_factory=Fleet)
    stuck: Stuck = Field(default_factory=Stuck)
    broker: dict[str, Credential] = {}  # tool -> the credentials Cressey hands it
    decoys: dict[str, str] = {}  # trap key name -> value: a call carrying one is caught


class Catalog(BaseModel):
    """What one surface's own tools do (catalogs/), such as Claude Code's through the hook."""

    surface: Surface
    tools: dict[str, ToolRule]


class Profile(BaseModel):
    """A deployment: what Cressey fronts. `demo` is the demo's own tools; otherwise the MCP
    servers, as MCP clients configure them ({"mcpServers": {name: {"url": …}}})."""

    upstreams: Literal["demo"] | dict[str, JsonValue]
    tools: dict[str, ToolRule] = {}  # what each of its tools does
    broker: dict[str, Credential] = {}
    decoys: dict[str, str] = {}


def load_profile(path: Path) -> Profile:
    return Profile.model_validate(yaml.safe_load(path.read_text()))


def load_policy(data: Path, profile: Profile) -> Policy:
    """The engine's settings in `data`, and each surface's tools: its catalogs', and the
    profile's for the MCP gateway. A tool listed twice for one surface would be classified by
    whichever file came last, so it is refused; one name on two surfaces is two tools."""
    tools: dict[Surface, dict[str, ToolRule]] = {s: {} for s in get_args(Surface)}
    tools["mcp"] |= profile.tools
    for catalog in sorted((data / "catalogs").glob("*.yaml")):
        listed = Catalog.model_validate(yaml.safe_load(catalog.read_text()))
        if twice := tools[listed.surface].keys() & listed.tools.keys():
            raise ValueError(f"{catalog.name} lists {sorted(twice)} again")
        tools[listed.surface] |= listed.tools
    settings = yaml.safe_load((data / "policy.yaml").read_text())
    return Policy.model_validate(
        {**settings, "tools": tools, "broker": profile.broker, "decoys": profile.decoys}
    )
