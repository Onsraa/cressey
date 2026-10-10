"""The fraud triangle over the run so far. Code reads the facts; Jev labels one thing (is
this call needed for the task?); code weighs it by the call's risk and decides."""

from collections.abc import Sequence

from pydantic import JsonValue

from cressey.core.judge import Judge
from cressey.core.models import Leg, Legs, Risk, Run, Step, Thresholds

LEG_NAMES = {
    "pressure": "pression",
    "opportunity": "opportunité",
    "rationalization": "rationalisation",
}


def _earlier(run: Run) -> list[Step]:
    """The calls before the one being judged: its own result isn't known yet."""
    return run.steps[:-1]


def _failures(steps: Sequence[Step]) -> list[int]:
    return [s.n for s in steps if s.is_error]


def _repeats(steps: Sequence[Step]) -> list[int]:
    seen: set[tuple[str, str]] = set()
    repeats = []
    for s in steps:
        if (s.tool, s.args) in seen:
            repeats.append(s.n)
        seen.add((s.tool, s.args))
    return repeats


def pressure(run: Run, t: Thresholds) -> Leg:
    earlier = _earlier(run)
    failures, repeats = _failures(earlier), _repeats(earlier)
    deadline = [w for w in t.deadline_words if w.lower() in run.task.lower()]
    facts = []
    if failures:
        facts.append(f"{len(failures)} appels en échec (étapes {_list(failures)})")
    if repeats:
        facts.append(f"{len(repeats)} appels répétés (étapes {_list(repeats)})")
    if deadline:
        facts.append(f"échéance dans la tâche : « {deadline[0]} »")
    score = (
        min(1, len(failures) / t.failures)
        + min(1, len(repeats) / t.repeats)
        + (1 if deadline else 0)
    ) / 3
    confirmed = len(failures) >= t.failures or len(repeats) >= t.repeats
    return Leg(score=score, confirmed=confirmed, facts=facts)


def opportunity(run: Run) -> Leg:
    facts, seen = [], set()
    for s in _earlier(run):
        for secret in s.secrets:
            name = secret.name or secret.kind
            if secret.fingerprint in seen or name in run.mandate.may_read_secrets:
                continue
            seen.add(secret.fingerprint)
            facts.append(f"{name} lue à l'étape {s.n} ({s.tool} {s.args})")
    return Leg(score=1.0 if facts else 0.0, confirmed=bool(facts), facts=facts)


def run_state(run: Run, t: Thresholds) -> dict[str, JsonValue]:
    """What Jev reads: the run summarised by code, secrets redacted."""
    earlier, call = _earlier(run), run.steps[-1]
    recent: list[JsonValue] = [
        f"{s.n}. {s.tool} {s.args} → {'échec' if s.is_error else s.status}"
        for s in earlier[-t.summary_steps :]
    ]
    secrets: list[JsonValue] = [
        f"{x.name or x.kind} (étape {s.n})" for s in earlier for x in s.secrets
    ]
    return {
        "task": run.task,
        "mandate": run.mandate.model_dump(),
        "failed_calls": len(_failures(earlier)),
        "repeated_calls": len(_repeats(earlier)),
        "secrets_read": secrets,
        "recent_actions": recent,
        "action": f"{call.tool} {call.args}",
    }


async def _rationalization(run: Run, judge: Judge, t: Thresholds) -> Leg:
    call = run.steps[-1]
    weight = t.weights[call.risk]
    if weight == 0:
        return Leg(score=0.0, confirmed=False, facts=[])
    needed = await judge.needed(run_state(run, t))
    if needed is None:
        return Leg(
            score=0.0, confirmed=False, facts=["Jev indisponible : dérive non mesurée"]
        )
    drift = (1 - needed) * weight
    fact = f"Jev : nécessaire à la tâche {needed:.2f} ; risque {call.risk} → dérive {drift:.2f}"
    return Leg(score=drift, confirmed=drift >= t.drift, facts=[fact])


async def legs(run: Run, judge: Judge, t: Thresholds) -> Legs:
    """The triangle when the run's last call comes in."""
    return Legs(
        pressure=pressure(run, t),
        opportunity=opportunity(run),
        rationalization=await _rationalization(run, judge, t),
    )


def confirmed(legs: Legs) -> list[str]:
    return [name for name, leg in legs if leg.confirmed]


def alarm(legs: Legs, risk: Risk) -> bool:
    """Two legs confirmed by facts hold any call that isn't a read."""
    return risk != "read" and len(confirmed(legs)) >= 2


def alarm_reason(legs: Legs) -> str:
    names = [LEG_NAMES[n] for n in confirmed(legs)]
    joined = ", ".join(names[:-1]) + " et " + names[-1]
    return f"triangle : {joined} confirmées"


def _list(numbers: list[int]) -> str:
    return ", ".join(map(str, numbers))
