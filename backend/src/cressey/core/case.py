"""The case file: events grouped into threads by object, and the §7 decision for a call.

Pure: no model call and no clock. A thread is a P or an O object with a state; R and C1 stay
events, they are not about one obstacle or access. `decide` is the shadow: what Cressey
would do with a tool call given the case so far.
"""

import re
from collections.abc import Mapping

from cressey.core.models import (
    Case,
    Event,
    Mandate,
    Note,
    Run,
    Shadow,
    Step,
    Thread,
    Thresholds,
)
from cressey.guide.models import Leg

# An indicator that belongs to no leg (plan, the N counters) is absent.
LEG: dict[str, Leg] = {
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
    """The mandate covers this object: a human approved it, or it is a secret it names."""
    if obj in case.approved:
        return True
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
    built: dict[tuple[Leg, str | None], Thread] = {}
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
        if t.object in case.approved:
            t.state = "approved"
        elif t.object in named["N2"]:
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


def notes(run: Run, after: int) -> list[Note]:
    """What the case warrants before any act, `after` calls in: a way out for an obstacle
    never shared, an alert for a probe, a weak control or a plan to hide a trace."""
    case = run.case
    out: list[Note] = []
    if unshared := _unshared(case):
        why = "; ".join(f'Never shared: "{_quote(case, th)}"' for th in unshared)
        out.append(Note(after=after, action="way_out", why=why))
    if probes := _probes(case):
        why = "; ".join(f'{e.indicator}: "{e.quote}"' for e in probes)
        out.append(Note(after=after, action="alert", why=why))
    return out
