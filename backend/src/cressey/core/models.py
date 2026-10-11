"""Types of the core loop: the tool policy, a task's mandate, runs and their steps."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from cressey.core.secret_scan import Secret
from cressey.core.trace import How
from cressey.guide.models import Leg as LegName
from cressey.guide.models import OwnerRole

Risk = Literal["read", "write", "destructive"]
# What Cressey sees: tool calls only; plus messages and report; plus reasoning.
Visibility = Literal["tools", "messages", "reasoning"]
# control: « Observateur », logged and never held. replay: never waits for a human; a call
# that would be held is blocked, and that replay fails.
RunKind = Literal["live", "replay", "control"]
# What Cressey does with a call a check fired on: let it through with an incident, hold it
# for a human, or refuse it at once.
Response = Literal["alert", "review", "stop"]


class ToolRule(BaseModel):
    kind: Literal["read", "write", "destructive", "sql", "egress", "shell"]
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


class Fleet(BaseModel):
    """When runs held for the same target outside their mandate become a signal across runs
    (policy.yaml, `fleet`)."""

    runs: int = 3  # distinct runs held for that target
    window_minutes: int = 15


class FleetSignal(BaseModel):
    target: str  # the tool and the floor's reason: « run_sql | SQL destructeur hors mandat : users »
    runs: list[str]  # the runs held for it within the window, oldest first
    first_at: str
    last_at: str


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
    triangle: Response = "review"  # the judgment, with pressure or opportunity
    fleet: Literal["alert", "stop"] = (
        "alert"  # stop: once the signal is up, refuse its target
    )


class Policy(BaseModel):
    tools: dict[str, ToolRule]
    responses: Responses = Field(default_factory=Responses)
    triangle: Thresholds = Field(default_factory=Thresholds)
    fleet: Fleet = Field(default_factory=Fleet)
    broker: dict[str, Credential] = {}  # tool -> the credentials Cressey hands it
    decoys: dict[str, str] = {}  # trap key name -> value: any call carrying one is held


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
        "allowed",
        "alerted",
        "held",
        "approved",
        "rejected",
        "expired",
        "denied",
        "would_hold",
    ] = "allowed"
    reason: str | None = None
    is_error: bool = False
    secrets: list[Secret] = []  # found in what the call returned; names, never values
    held_until: str | None = None
    decided_at: str | None = None
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


class Message(BaseModel):
    after: int  # how many calls the agent had made when it said this
    text: str  # agent text, secrets redacted
    # The user's prompt (Claude Code's UserPromptSubmit) is shown, never scored as the agent's.
    role: Literal["agent", "user"] = "agent"
    streaming: bool = False  # still arriving, slice by slice


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
    revoked: bool = False
    # Acting on pressure, without a human: the step whose result carried the way out, and
    # the step from which the key refuses destructive calls.
    way_out_step: int | None = None
    read_only_step: int | None = None
    steps: list[Step] = []
    messages: list[Message] = []
    report: str | None = None  # the agent's final report: agent text, secrets redacted
    report_check: Leg | None = None  # that report against the log (S9)
    preflight: Preflight | None = None  # set in the background, after the run starts
    ended_at: str | None = None
    # Claude Code's turn, from its hooks: waiting for a prompt, or working on one. None until
    # a session starts, and for an MCP agent.
    turn: Literal["waiting", "working"] | None = None
    # Never served: the steps before this one no longer keep the key suspended (the user's
    # prompt unlocked it), and the Claude Code session this run follows.
    unlocked_after: int = Field(default=0, exclude=True)
    session: str | None = Field(default=None, exclude=True)
    # Secret value -> fingerprint, to redact it wherever it shows up later. Never served.
    known: dict[str, str] = Field(default_factory=dict, exclude=True)


class TextIn(BaseModel):
    """A message or the final report, from the agent."""

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
    mcp_path: str  # the MCP proxy agents point at
    hook_path: str  # the Claude Code hook agents post to
    log: LogHead


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
    created_at: str
    decision: str  # the held call's status when served
    sources: list[Source]
    legs: Legs
    guides: list[OwnerGuide]
    fixes: list[Fix] = []
    replay: Replay | None = None  # the last « Rejouer ×5 »


class EvalFile(BaseModel):
    """A measured report, served as written, with where and when it was measured."""

    kind: Literal["guides", "detection", "ablation", "decision"]
    split: str  # dev, or held-out
    file: str
    date: str
    report: dict[str, JsonValue]
