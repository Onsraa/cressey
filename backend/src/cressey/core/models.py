"""Types of the core loop: the tool policy, a task's mandate, runs and their steps."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue

Risk = Literal["read", "write", "destructive"]


class ToolRule(BaseModel):
    kind: Literal["read", "write", "destructive", "sql", "egress"]
    arg: str | None = None  # the argument holding the SQL or the recipients


class Policy(BaseModel):
    tools: dict[str, ToolRule]


class Mandate(BaseModel):
    may_destroy: list[str] = []  # tables the task may delete from or drop
    may_send_to: list[str] = []  # addresses, or "@domain"


class RunIn(BaseModel):
    task: str = Field(min_length=3, max_length=2000)
    mandate: Mandate = Field(default_factory=Mandate)


class RunCreated(BaseModel):
    id: str
    key: str  # shown once; Cressey keeps only its hash


class Step(BaseModel):
    n: int  # 1-based, as in « étape 4 »
    tool: str
    args: dict[str, JsonValue]
    risk: Risk
    status: Literal["allowed", "held", "approved", "rejected", "expired", "denied"] = (
        "allowed"
    )
    reason: str | None = None
    is_error: bool = False
    result: str = Field(
        "", exclude=True
    )  # what the agent read: kept for tracing, never served


class Run(BaseModel):
    id: str
    task: str
    mandate: Mandate
    started_at: str
    revoked: bool = False
    steps: list[Step] = []


class Hold(BaseModel):
    run_id: str
    task: str
    step: Step
