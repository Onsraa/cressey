"""An incident: one held call, where its values came from, a fix and a guide for each leg's
owner, and the « Rejouer ×5 » that checks the fixes; and the signal across runs."""

from typing import Literal

from pydantic import BaseModel

from cressey.domain.owners import LegName, OwnerRole
from cressey.domain.reasons import Check, Reason
from cressey.domain.runs import Legs, Preflight

How = Literal["exact", "lowercase", "base64", "hex", "url"]


class FleetSignal(BaseModel):
    target: str  # the tool and the floor's reason: « run_sql | destructive SQL outside the mandate: users »
    checks: list[Check]  # the checks that fired on it
    runs: list[str]  # the runs held for it within the window, oldest first
    first_at: str
    last_at: str


class OwnerGuide(BaseModel):
    leg: LegName
    owner_role: OwnerRole
    status: Literal["pending", "ok", "unsure", "unavailable"] = "pending"
    guide_id: str | None = None


class Source(BaseModel):
    """Where a value of the held call was first read."""

    step: int
    tool: str
    args: str  # that call's arguments, secrets redacted
    how: How  # exact, lowercase, base64, hex or url
    secret: str | None  # the secret's name, when the value is one
    value: str  # as matched; a secret shows as its marker


class Fix(BaseModel):
    """Cressey's proposal for one confirmed leg. A human approves it; the replay applies it."""

    leg: LegName
    owner_role: OwnerRole
    text: str  # what changes, for the owner
    move_out: list[str] = []  # workspace files the secret leaves
    add_to_task: str | None = None  # appended to the task
    preflight: Preflight | None = None  # the fixed task, assessed: the before and after
    approved: bool = False


class ReplayResult(BaseModel):
    session: str
    expect: Literal["held", "free"]
    # Cressey refused a call, the agent stopped on a call it needed, or it finished.
    outcome: Literal["refused", "stopped", "completed"]
    step: int | None  # the refused call, or the one that stopped the agent
    reason: str | None  # Cressey's reason, for a refusal
    ok: bool  # a variant must stop on its own; a normal task must finish


class Replay(BaseModel):
    """« Rejouer ×5 »: a regression test of the policy and the fixes on scripted sessions,
    not proof of how a real agent behaves."""

    date: str
    fixes: list[LegName]  # the approved fixes it played with
    results: list[ReplayResult]
    passed: bool


class Incident(BaseModel):
    id: str
    run_id: str
    step: int
    severity: Literal["critique", "haute"]  # safety floor, or two confirmed legs
    reason: str
    reasons: list[Reason] = []  # the checks that fired, `reason` their text
    created_at: str
    decision: str  # the held call's status when served
    sources: list[Source]
    legs: Legs
    guides: list[OwnerGuide]
    fixes: list[Fix] = []
    replay: Replay | None = None  # the last « Rejouer ×5 »
