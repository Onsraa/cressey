"""Types of the core loop: the tool policy, a task's mandate, runs and their steps."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from cressey.core.secret_scan import Secret

Risk = Literal["read", "write", "destructive"]
# What Cressey sees: tool calls only; plus messages and report; plus reasoning.
Visibility = Literal["tools", "messages", "reasoning"]
# control: « Observateur », logged and never held. replay: never waits for a human; a call
# that would be held is blocked, and that replay fails.
RunKind = Literal["live", "replay", "control"]


class ToolRule(BaseModel):
    kind: Literal["read", "write", "destructive", "sql", "egress"]
    arg: str | None = None  # the argument holding the SQL or the recipients


class Thresholds(BaseModel):
    """When observed facts confirm a leg (policy.yaml, `triangle`)."""

    failures: int = 2  # failed calls that confirm pressure
    repeats: int = 2  # identical calls repeated that confirm pressure
    drift: float = 0.5  # risk-weighted drift that confirms rationalization
    summary_steps: int = 8  # recent actions Jev sees
    deadline_words: list[str] = []
    # S2: run_tests on a typo fix scored 0.15 "needed", so drift is weighted by risk.
    weights: dict[Risk, float] = {"read": 0.0, "write": 0.5, "destructive": 1.0}


class Policy(BaseModel):
    tools: dict[str, ToolRule]
    triangle: Thresholds = Field(default_factory=Thresholds)


class Mandate(BaseModel):
    may_destroy: list[str] = []  # tables the task may delete from or drop
    may_send_to: list[str] = []  # addresses, or "@domain"
    may_read_secrets: list[str] = []  # names of the secrets the task needs


class Leg(BaseModel):
    score: float  # 0 to 1, for the gauge
    confirmed: bool  # facts observed by code confirm it
    facts: list[str]


class Legs(BaseModel):
    pressure: Leg
    opportunity: Leg
    rationalization: Leg


class RunIn(BaseModel):
    task: str = Field(min_length=3, max_length=2000)
    mandate: Mandate = Field(default_factory=Mandate)
    visibility: Visibility = "tools"
    kind: RunKind = "live"


class RunCreated(BaseModel):
    id: str
    key: str  # shown once; Cressey keeps only its hash


class Step(BaseModel):
    n: int  # 1-based, as in « étape 4 »
    tool: str
    args: str  # the arguments as JSON, secrets redacted
    risk: Risk
    status: Literal[
        "allowed", "held", "approved", "rejected", "expired", "denied", "would_hold"
    ] = "allowed"
    reason: str | None = None
    is_error: bool = False
    secrets: list[Secret] = []  # found in what the call returned; names, never values
    held_until: str | None = None
    decided_at: str | None = None
    legs: Legs | None = None  # the triangle when this call came in
    # Kept in memory for tracing, never served.
    raw_args: dict[str, JsonValue] = Field(default_factory=dict, exclude=True)
    result: str = Field("", exclude=True)


class Run(BaseModel):
    id: str
    task: str
    mandate: Mandate
    visibility: Visibility
    kind: RunKind
    started_at: str
    revoked: bool = False
    steps: list[Step] = []
    report: str | None = None  # the agent's final report: agent text, secrets redacted
    ended_at: str | None = None
    # Secret value -> fingerprint, to redact it wherever it shows up later. Never served.
    known: dict[str, str] = Field(default_factory=dict, exclude=True)


class ReportIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class Hold(BaseModel):
    run_id: str
    task: str
    step: Step


class LogHead(BaseModel):
    hash: str
    count: int
    intact: bool


class Status(BaseModel):
    mode: Literal["guard"]  # the only protection mode built so far
    model_mode: str
    mcp_path: str
    log: LogHead
