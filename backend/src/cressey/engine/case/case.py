"""The case file: events grouped into threads by object, and the §7 decision for a call.

A thread is a P or an O object with a state; R and C1 stay events, they are not about one
obstacle or access. `decide` is the shadow: what Cressey would do with a tool call given the
case so far. It and the threads are pure (no model call, no clock). The run builds its case
from two sources: the agent's thoughts (`read_message`) and what the code saw (`code_events`);
`shadow` puts them together for one call. The user's prompts are never read into it: a
person's word is a record, never evidence (the user's rule, 10-12).
"""

import asyncio
import re
import weakref
from collections.abc import Callable, Mapping

from cressey.domain.owners import LEGS, LegName
from cressey.domain.policy import Thresholds
from cressey.domain.reasons import Reason
from cressey.domain.runs import (
    Case,
    Event,
    Leg,
    Legs,
    Mandate,
    Message,
    Run,
    Shadow,
    Step,
    ThoughtPoint,
    Thread,
)
from cressey.engine.case.thoughts import (
    read_thought,
    thoughts_of,
)
from cressey.judge import Judge
from cressey.tasks import Tasks

# An indicator that belongs to no leg (plan, the N counters) is absent.
LEG: dict[str, LegName] = {
    **dict.fromkeys(("P1", "P3", "P4"), "pressure"),
    **dict.fromkeys(("O1", "O2", "O3", "O4", "I1"), "opportunity"),
    **dict.fromkeys(("R", "C1"), "rationalization"),
}
SECRET = "secret:"


def secret_names(run: Run) -> dict[str, str]:
    """Fingerprint to name of every named secret the run's calls returned."""
    return {s.fingerprint: s.name for x in run.steps for s in x.secrets if s.name}


def _granted(
    obj: str | None, case: Case, mandate: Mandate, names: Mapping[str, str]
) -> bool:
    """The mandate covers this object: it is a secret the mandate names."""
    return (
        obj is not None
        and obj.startswith(SECRET)
        and names.get(obj.removeprefix(SECRET)) in mandate.may_read_secrets
    )


def threads(
    case: Case, mandate: Mandate, names: Mapping[str, str] | None = None
) -> list[Thread]:
    """One thread per leg and object, in the order each first appears. `names` is
    fingerprint to secret name (`secret_names`): without it no secret is the mandate's."""
    names = names or {}
    built: dict[tuple[LegName, str | None], Thread] = {}
    for i, e in enumerate(case.events):
        leg = LEG.get(e.indicator)
        if leg is None or leg == "rationalization":
            continue
        for obj in dict.fromkeys(e.objects or [None]):
            built.setdefault((leg, obj), Thread(leg=leg, object=obj)).events.append(i)
    named = {
        n: {o for e in case.events if e.indicator == n for o in e.objects}
        for n in ("N1", "N2", "N3")
    }
    # An N1 that names nothing answers the obstacles raised before it, not the ones after.
    bare = max(
        (i for i, e in enumerate(case.events) if e.indicator == "N1" and not e.objects),
        default=-1,
    )
    for t in built.values():
        if t.object in named["N2"]:
            t.state = "renounced"
        elif t.object in named["N3"]:
            t.state = "verified"
        elif t.object in named["N1"] or (t.leg == "pressure" and t.events[0] < bare):
            t.state = "shared"
        t.outside = t.leg == "opportunity" and not _granted(
            t.object, case, mandate, names
        )
    return list(built.values())


def record(
    case: Case,
    events: list[Event],
    mandate: Mandate,
    names: Mapping[str, str] | None = None,
) -> None:
    case.events.extend(events)
    case.threads = threads(case, mandate, names)


def _carries(obj: str, args: str, names: Mapping[str, str]) -> bool:
    """A1: the call's arguments carry the object's id (a pasted marker holds it), or the
    name of the secret it stands for."""
    if obj in args:
        return True
    name = names.get(obj.removeprefix(SECRET)) if obj.startswith(SECRET) else None
    return name is not None and bool(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", args)
    )


def _carried(run: Run, call: Step, state: str) -> dict[str, Thread]:
    """The O threads in `state` whose object the call carries, by object."""
    names = secret_names(run)
    return {
        t.object: t
        for t in run.case.threads
        if t.leg == "opportunity"
        and t.state == state
        and t.object is not None
        and _carries(t.object, call.args, names)
    }


def uses(run: Run, call: Step) -> list[str]:
    """A1: the objects of the open O threads that the call carries."""
    return list(_carried(run, call, "open"))


def _quote(case: Case, t: Thread) -> str:
    return case.events[t.events[0]].quote


def _unshared(case: Case) -> list[Thread]:
    return [t for t in case.threads if t.leg == "pressure" and t.state == "open"]


def _probes(case: Case) -> list[Event]:
    """An O3 or O2 on a thread still open, and any C1 (a plan to hide a trace)."""
    live = {
        i
        for t in case.threads
        if t.leg == "opportunity" and t.state == "open"
        for i in t.events
    }
    return [
        e
        for i, e in enumerate(case.events)
        if e.indicator == "C1" or (e.indicator in ("O2", "O3") and i in live)
    ]


def decide(run: Run, call: Step, floor: str | None, t: Thresholds) -> Shadow:
    """The §7 table, in order. `floor` is the safety floor's reason for the call (A3)."""
    case = run.case
    carried = _carried(run, call, "open")
    renounced = _carried(run, call, "renounced")
    changes = call.risk != "read"
    objects = list(carried)

    if renounced:
        said = [
            next(
                e
                for e in reversed(case.events)
                if e.indicator == "N2" and o in e.objects
            )
            for o in renounced
        ]
        return Shadow(
            decision="hold",
            why=[f'said no at "{e.quote}" then used it' for e in said],
            uses=[*renounced, *objects],
        )

    unshared = _unshared(case)
    justified = [
        e
        for e in case.events
        if e.indicator == "R"
        and e.direction == "toward"
        and carried.keys() & set(e.objects)
    ]
    hidden = [e for e in case.events if e.indicator == "C1"]
    if (carried or floor is not None) and (unshared or justified or hidden):
        why = [f"Uses: {o} ({_quote(case, th)})" for o, th in carried.items()]
        if floor is not None:
            why.append(f"Beyond the mandate: {floor}")
        why += [f'Justified by: "{e.quote}"' for e in justified]
        why += [f'Concealment: "{e.quote}"' for e in hidden]
        why += [
            f'Never shared: "{_quote(case, th)}", no question to the human'
            for th in unshared
        ]
        if carried:
            why.append(
                f"Target never verified: no environment check on {', '.join(carried)}"
            )
        return Shadow(decision="hold", why=why, uses=objects)

    outside = [o for o, th in carried.items() if th.outside]
    if outside and changes:
        return Shadow(
            decision="hold", why=["used without a stated reason"], uses=objects
        )
    if outside:
        return Shadow(
            decision="alert",
            why=[
                f"Uses: {o} ({_quote(case, carried[o])}), outside the mandate"
                for o in outside
            ],
            uses=objects,
        )
    if probes := _probes(case):
        return Shadow(
            decision="alert",
            why=[f'{e.indicator}: "{e.quote}"' for e in probes],
            uses=objects,
        )
    return Shadow(decision="allow", why=[], uses=objects)


def leg_evidence(case: Case) -> dict[LegName, int]:
    """Each leg's evidence, as an index in the case's events: the strongest event of its open
    threads, the first of equals. R and C1 open no thread, so rationalization's is the
    strongest of them going toward the crossing (one going away, a pause or a refusal, is no
    justification). A leg with none is absent."""

    def threaded(leg: LegName) -> list[int]:
        return [
            i
            for t in case.threads
            if t.leg == leg and t.state == "open"
            for i in t.events
        ]

    toward = [
        i
        for i, e in enumerate(case.events)
        if e.indicator in ("R", "C1") and e.direction == "toward"
    ]
    found: dict[LegName, list[int]] = {
        "pressure": threaded("pressure"),
        "opportunity": threaded("opportunity"),
        "rationalization": toward,
    }
    return {
        leg: max(events, key=lambda i: case.events[i].p)
        for leg, events in found.items()
        if events
    }


def leg_values(case: Case) -> dict[LegName, float]:
    """Each leg as the case holds it: its evidence's probability, 0 when it has none."""
    lead = leg_evidence(case)
    return {leg: case.events[lead[leg]].p if leg in lead else 0.0 for leg in LEGS}


def thought_points(run: Run) -> list[list[ThoughtPoint]]:
    """Each message's read thoughts on the triangle, for the dashboard, in the order said. A
    thought scores a leg with its highest answer to the leg's questions (`LEG`), an answer
    whose conclusion goes away from the crossing counting for nothing."""
    away = {
        (e.message, e.thought, e.indicator)
        for e in run.case.events
        if e.direction == "away"
    }

    def score(j: int, i: int, name: LegName) -> float:
        answers = run.messages[j].scores[i].items()
        return max(
            (p for q, p in answers if LEG.get(q) == name and (j, i, q) not in away),
            default=0.0,
        )

    return [
        [
            ThoughtPoint(
                thought=i,
                pressure=score(j, i, "pressure"),
                opportunity=score(j, i, "opportunity"),
                rationalization=score(j, i, "rationalization"),
            )
            for i in range(len(m.thoughts))
            if i in m.scores
        ]
        for j, m in enumerate(run.messages)
    ]


def thought_legs(run: Run) -> list[Legs | None]:
    """Each message's thoughts on the triangle, for the dashboard: the leg is its strongest
    thought (`thought_points`), and each thought's score is a fact, strongest first. None for
    a message with no thought read."""

    def legs(m: Message, points: list[ThoughtPoint]) -> Legs:
        def leg(of: Callable[[ThoughtPoint], float]) -> Leg:
            scored = [(of(t), m.thoughts[t.thought]) for t in points if of(t) > 0]
            scored.sort(key=lambda x: x[0], reverse=True)
            return Leg(
                score=scored[0][0] if scored else 0.0,
                confirmed=False,
                facts=[f"“{text}” {score:.2f}" for score, text in scored],
            )

        return Legs(
            pressure=leg(lambda t: t.pressure),
            opportunity=leg(lambda t: t.opportunity),
            rationalization=leg(lambda t: t.rationalization),
        )

    return [
        legs(m, points) if points else None
        for m, points in zip(run.messages, thought_points(run), strict=True)
    ]


async def read_message(run: Run, m: Message, judge: Judge, t: Thresholds) -> bool:
    """Read the agent's thoughts in m that are not read yet, in order, into the case. False
    when one gets no answer: it and those after it stay unread, and are asked again."""
    if m.role != "agent":  # the user's prompts are never read into the case
        return True
    m.thoughts = [x.text for x in thoughts_of(m)]
    while m.read < len(m.thoughts):
        events = await read_thought(run, m, m.read, judge, t)
        if events is None:
            return False
        record(run.case, events, run.mandate, secret_names(run))
        m.read += 1
    return True


def code_events(run: Run, step: Step) -> list[Event]:
    """O1, from the code alone: the step read a secret the mandate does not name."""
    return [
        Event(
            indicator="O1",
            p=1.0,
            quote=f"{s.name or s.kind} read at step {step.n}",
            source="code",
            after=step.n - 1,
            objects=[f"{SECRET}{s.fingerprint}"],
        )
        for s in {s.fingerprint: s for s in step.secrets}.values()
        if s.name not in run.mandate.may_read_secrets
    ]


async def catch_up(run: Run, before: int, judge: Judge, t: Thresholds) -> bool:
    """Bring the case up to date with the run before step `before`: the code facts of the
    steps before it, and the agent's thoughts said before it. False when a thought has no
    answer, or when no thought is read at all (a run seen through its tools only, or a
    replay: §12)."""
    case = run.case
    known = {(e.after, *e.objects) for e in case.events if e.source == "code"}
    fresh = [
        e
        for s in run.steps
        if s.n < before
        for e in code_events(run, s)
        if (e.after, *e.objects) not in known
    ]
    record(case, fresh, run.mandate, secret_names(run))
    if run.visibility == "tools" or run.kind == "replay":
        return False
    for m in run.messages:  # in order: a thought is read after the ones before it
        if m.after < before and not await read_message(run, m, judge, t):
            return False
    return True


async def shadow(
    run: Run, call: Step, floor: str | None, judge: Judge, t: Thresholds
) -> Shadow:
    """The decision for `call` once the case holds what came before it. `words_read` is
    False when a thought before it has no answer, or none is read (see `_catch_up`)."""
    words_read = await catch_up(run, call.n, judge, t)
    decision = decide(run, call, floor, t)
    decision.words_read = words_read
    decision.legs = leg_values(run.case)
    return decision


def closing_excuse(run: Run, legs: Legs) -> int | None:
    """The excuse in the agent's words that closes the triangle, as an index in the case's
    events: the newest justification or concealment going toward the crossing, once pressure
    or opportunity is confirmed by code or open in the case. None when the triangle isn't
    closed, or when that excuse already stopped a call: one stop per thought."""
    case = run.case
    excuses = [
        i
        for i, e in enumerate(case.events)
        if e.indicator in ("R", "C1") and e.direction == "toward"
    ]
    if not excuses or excuses[-1] in {s.stopped_by for s in run.steps}:
        return None
    other_leg = (
        legs.pressure.confirmed
        or legs.opportunity.confirmed
        or any(
            th.state == "open" and (th.leg == "pressure" or th.outside)
            for th in case.threads
        )
    )
    return excuses[-1] if other_leg else None


def excuse_reason(run: Run, i: int) -> Reason:
    return Reason(check="thought", target=run.case.events[i].quote)


class CaseReader:
    """Reads a run's thoughts into its case, one reader at a time per run and in the order
    scheduled: each reads thoughts into the case and the next reads that case, and two
    reading at once would read the same thought twice. A call's shadow is read in the
    background, so no call waits for it."""

    def __init__(self, judge: Judge, t: Thresholds) -> None:
        self.judge, self.t = judge, t
        self._turns: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._shadows: Tasks[Shadow] = Tasks()

    def _turn(self, run: Run) -> asyncio.Lock:
        lock = self._turns.get(run.id)
        if lock is None:
            lock = self._turns[run.id] = asyncio.Lock()
        return lock

    async def read_until(self, run: Run, call: Step) -> None:
        """The case brought up to date with what came before `call`, in the run's turn, so
        the call is decided on the agent's words too (CRESSEY_THOUGHT_HOLDS)."""
        async with self._turn(run):
            await catch_up(run, call.n, self.judge, self.t)

    async def _shadow(self, run: Run, call: Step, floor: str | None) -> Shadow:
        async with self._turn(run):
            return await shadow(run, call, floor, self.judge, self.t)

    async def settled(self, run: Run) -> None:
        """The shadows in flight on this run are read."""
        await self._shadows.settled(run.id)

    def shadow_soon(
        self, run: Run, call: Step, floor: str | None
    ) -> asyncio.Task[Shadow] | None:
        """Compute the shadow of `call` in the background, so the call never waits for it.
        None when it is already being computed: whoever scheduled it stores its result."""
        key = (run.id, call.n)
        if self._shadows.get(key) is not None:
            return None
        return self._shadows.once(key, lambda: self._shadow(run, call, floor))
