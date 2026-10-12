"""A run and what it is made of: its task and mandate, each call (step), what the agent said,
and the case built from its thoughts."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from cressey.domain.acts import Agent, Asker, Surface
from cressey.domain.owners import LegName
from cressey.domain.reasons import Reason, joined

Risk = Literal["read", "write", "destructive"]
# What Cressey sees: tool calls only; plus messages and report; plus reasoning.
Visibility = Literal["tools", "messages", "reasoning"]
# control: « Observateur », logged and never held. replay: never waits for a human; a call
# that would be held is blocked, and that replay fails.
RunKind = Literal["live", "replay", "control"]
# Where the agent's words come from: its narration, a summary of its reasoning, or its
# reasoning itself.
WordSource = Literal["narration", "summary", "reasoning"]
EventSource = Literal[
    "narration", "summary", "reasoning", "code", "environment", "task"
]
Indicator = Literal[
    "P1",
    "P3",
    "P4",
    "O1",
    "O2",
    "O3",
    "O4",
    "R",
    "C1",
    "N1",
    "N2",
    "N3",
    "N4",
    "I1",
    "plan",
]
Kind = Literal[
    "necessity",
    "override",
    "normalization",
    "minimization",
    "borrowed_authority",
    "reframed_goal",
    "blame_check",
    "other",
]
Direction = Literal["toward", "away", "neither"]


class Secret(BaseModel):
    kind: str  # detect-secrets plugin name, or "Named secret" for the naming rule
    name: str | None  # the variable name, when the naming rule matched
    fingerprint: str  # first 12 hex chars of sha256(value)
    line: int  # 1-based


class Mandate(BaseModel):
    may_destroy: list[
        str
    ] = []  # tables the task may change rows in, delete from or drop
    may_send_to: list[str] = []  # addresses, or "@domain"
    may_read_secrets: list[str] = []  # names of the secrets the task needs
    # Paths the agent may neither read nor write: a scorer, other runs, secret stores.
    # A name protects everything under it; globs work too.
    protected: list[str] = []
    # Paths the agent may read but not write: the tests, a grader.
    frozen: list[str] = []


class Leg(BaseModel):
    score: float  # 0 to 1, for the gauge
    confirmed: bool  # facts observed by code confirm it
    facts: list[str]


class Legs(BaseModel):
    pressure: Leg
    opportunity: Leg
    rationalization: Leg


def confirmed(legs: Legs) -> list[str]:
    """The names of the legs facts confirm."""
    return [name for name, leg in legs if leg.confirmed]


class RunIn(BaseModel):
    task: str = Field(min_length=3, max_length=2000)
    mandate: Mandate = Field(default_factory=Mandate)
    visibility: Visibility = "tools"
    kind: RunKind = "live"


class RunCreated(BaseModel):
    id: str
    key: str  # shown once; Cressey keeps only its hash


class Event(BaseModel):
    indicator: Indicator
    p: float  # the model's probability; 1.0 for a code fact
    quote: str  # the thought verbatim (redacted), or the code fact
    source: EventSource
    after: int  # calls made before it
    message: int | None = None  # index in run.messages
    thought: int | None = None  # index in that message's thoughts
    objects: list[str] = []
    kind: Kind | None = None  # R only
    direction: Direction | None = None  # R and C1 only


class Thread(BaseModel):
    leg: LegName
    object: str | None = None
    state: Literal["open", "shared", "renounced", "verified", "approved"] = "open"
    outside: bool = False  # O: beyond what the mandate grants
    events: list[int] = []  # indexes in Case.events


class Case(BaseModel):
    events: list[Event] = []
    threads: list[Thread] = []
    approved: list[str] = []  # objects a human approved
    # Served only: each leg's evidence, an index in `events` (`case.leg_evidence`), the quote
    # its gauge shows. A leg with none is absent.
    evidence: dict[LegName, int] = {}


class Shadow(BaseModel):
    decision: Literal["allow", "alert", "hold"]
    why: list[str]  # the case, one line per link, as §7 writes it
    uses: list[str] = []  # case objects the call carries
    words_read: bool = True  # False when a thought before the call has no answer
    # Each leg as the case held it when the call came in (`case.leg_values`). Display only:
    # the dashboard raises the call's scores to it; no hold reads it.
    legs: dict[LegName, float] = {}


class Step(BaseModel):
    n: int  # 1-based, as in « étape 4 »
    # Its act: through which surface, by whom on which model, on whose request. None and
    # empty for a step a log written before acts were recorded gave back.
    surface: Surface | None = None
    agent: Agent = Field(default_factory=Agent)
    asked_by: list[Asker] = []
    tool: str
    args: str  # the arguments as JSON, secrets redacted
    risk: Risk
    status: Literal[
        "allowed",
        "alerted",
        "held",
        "approved",
        "rejected",
        "expired",
        "denied",
        "would_hold",
    ] = "allowed"
    reason: str | None = None  # the reasons, as the dashboard shows them
    reasons: list[Reason] = []  # why Cressey held, alerted on or refused it
    is_error: bool = False
    secrets: list[Secret] = []  # found in what the call returned; names, never values
    held_until: str | None = None
    decided_at: str | None = None
    # While held: what a rejection would tell the agent (the fallback, then a model's checked
    # draft); once rejected: what the human sent it.
    draft: str | None = None
    message: str | None = None
    legs: Legs | None = None  # the triangle when this call came in
    check_ms: float | None = (
        None  # Cressey's decision, before the tool runs or a hold waits
    )
    scan_ms: float | None = None  # the secret scan of what the call returned
    # Kept in memory for tracing, never served.
    raw_args: dict[str, JsonValue] = Field(default_factory=dict, exclude=True)
    result: str = Field("", exclude=True)
    # The ledger: the decision model's labels for this step, set once and never re-asked,
    # and for each flagged label the exact part that carries it (redacted).
    labels: dict[str, float] | None = Field(None, exclude=True)
    quotes: dict[str, str] = Field(default_factory=dict, exclude=True)
    # Its call may still return a result: a parallel call doesn't label it before that.
    # Served: the dashboard shows a tool running.
    running: bool = False
    shadow: Shadow | None = None
    # The excuse in the agent's words that stopped the agent at this call, as an index in
    # run.case.events (CRESSEY_THOUGHT_HOLDS); None when the words didn't stop it.
    stopped_by: int | None = None

    def because(self, reasons: list[Reason]) -> None:
        """Why Cressey held, alerted on or refused this call; the text follows the reasons."""
        self.reasons, self.reason = reasons, joined(reasons)


class RejectIn(BaseModel):
    """The reason a human gives the agent when they reject a held call."""

    message: str | None = Field(None, max_length=500)


class Message(BaseModel):
    after: int  # how many calls the agent had made when it said this
    text: str  # agent text, secrets redacted
    # The user's prompt (Claude Code's UserPromptSubmit) is shown, never scored as the agent's.
    role: Literal["agent", "user"] = "agent"
    streaming: bool = False  # still arriving, slice by slice
    source: WordSource = "narration"
    thoughts: list[str] = []  # the text of each thought
    read: int = 0  # how many of the thoughts are already read
    # Each read thought's answer to every question, by its index in `thoughts`, those under
    # their threshold too: the dashboard scores the thought on the triangle. Display only.
    scores: dict[int, dict[str, float]] = {}
    # Served only: its thoughts on the triangle (`case.thought_legs`); None until one is read.
    legs: Legs | None = None


class Preflight(BaseModel):
    """The task and its mandate, assessed before the run (« Avant le run »). Display only:
    no decision uses it."""

    scores: dict[str, float]  # each factor's answer; high means yes
    facts: list[str]  # the factors at risk: « libellé (p) → propriétaire : correction »


class Run(BaseModel):
    id: str
    task: str
    mandate: Mandate
    visibility: Visibility
    kind: RunKind
    started_at: str
    via: Literal["mcp", "hook"] | None = (
        None  # how its calls reach Cressey, for the badge
    )
    agent: Agent = Field(
        default_factory=Agent
    )  # who acts on it now, as the surface said
    revoked: bool = False
    # Holds rejected or expired since the user's last prompt (since the start for MCP, which
    # has none), and whether their number stopped the run: the key stays suspended until an
    # Unlock or the next prompt.
    refused: int = 0
    stopped: bool = False
    # Acting on pressure, without a human: the step whose result carried the way out, and
    # the step from which the key refuses destructive calls.
    way_out_step: int | None = None
    read_only_step: int | None = None
    steps: list[Step] = []
    messages: list[Message] = []
    case: Case = Field(default_factory=Case)
    report: str | None = None  # the agent's final report: agent text, secrets redacted
    report_check: Leg | None = None  # that report against the log (S9)
    preflight: Preflight | None = None  # set in the background, after the run starts
    ended_at: str | None = None
    # Claude Code's turn, from its hooks: waiting for a prompt, or working on one. None until
    # a session starts, and for an MCP agent.
    turn: Literal["waiting", "working"] | None = None
    # Never served: the Claude Code session this run follows.
    session: str | None = Field(default=None, exclude=True)
    # Secret value -> fingerprint, to redact it wherever it shows up later. Never served.
    known: dict[str, str] = Field(default_factory=dict, exclude=True)


class RunSummary(BaseModel):
    """A run as the dashboard polls it every second; the run itself is served on demand."""

    id: str
    task: str
    kind: RunKind
    via: Literal["mcp", "hook"] | None
    started_at: str
    calls: int

    @classmethod
    def of(cls, run: Run) -> "RunSummary":
        return cls(
            id=run.id,
            task=run.task,
            kind=run.kind,
            via=run.via,
            started_at=run.started_at,
            calls=len(run.steps),
        )


class TextIn(BaseModel):
    """A message or the final report, from the agent."""

    text: str = Field(min_length=1, max_length=5000)
    source: WordSource = "narration"


class Hold(BaseModel):
    run_id: str
    task: str
    step: Step
