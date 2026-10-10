"""One incident per held call: where its values came from, the legs that confirm it, and
a fix guide for each leg's owner, written in the background as soon as the call is held."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import JsonValue

from cressey.core.models import Incident, OwnerGuide, Run, Source, Step
from cressey.core.runs import Runs
from cressey.core.secret_scan import redact
from cressey.core.trace import trace
from cressey.guide.models import Guide, GuideIncident, OwnerRole
from cressey.guide.models import Leg as LegName

log = logging.getLogger(__name__)
LEGS: tuple[LegName, ...] = ("pressure", "opportunity", "rationalization")
OWNERS: dict[LegName, OwnerRole] = {
    "pressure": "task_author",
    "opportunity": "key_owner",
    "rationalization": "platform_owner",
}
ORDER = {"critique": 0, "haute": 1}


def _strings(value: JsonValue) -> list[str]:
    """Every string and number in the arguments: the trace reads raw values, not JSON."""
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return [] if value is None or isinstance(value, bool) else [str(value)]


def sources(run: Run, step: Step) -> list[Source]:
    earlier = run.steps[: step.n - 1]
    reads = [(s.n, s.result) for s in earlier if s.result]
    found = []
    for origin in trace(" ".join(_strings(step.raw_args)), reads):
        read = earlier[origin.step - 1]
        fingerprint = run.known.get(origin.token)
        secret = next(
            (x.name or x.kind for x in read.secrets if x.fingerprint == fingerprint),
            None,
        )
        # An encoded value taken from a call that exposed secrets shows only how it matched.
        shown = fingerprint is not None or not read.secrets
        found.append(
            Source(
                step=origin.step,
                tool=read.tool,
                args=read.args,
                how=origin.how,
                secret=secret,
                value=redact(origin.token, run.known) if shown else f"[{origin.how}]",
            )
        )
    return found


def _root_cause(
    name: LegName, incident: Incident, run: Run, step: Step
) -> tuple[str, str]:
    """(summary, source) for one leg's guide: a sentence built by code from the facts."""
    facts = " ; ".join(getattr(incident.legs, name).facts)
    action = f"{step.tool} {step.args}"
    secret = next((s for s in incident.sources if s.secret), None)
    if name == "pressure":
        summary = (
            f"La tâche pousse l'agent : {facts}. Il a ensuite tenté une action hors "
            f"mandat ({action}). Tâche : « {run.task} »."
        )
        return summary, "tâche"
    if name == "opportunity":
        used = (
            f"Il l'a utilisé dans {action}."
            if secret
            else f"Action retenue : {action}."
        )
        summary = f"Un secret dont la tâche n'a pas besoin était à la portée de l'agent : {facts}. {used}"
        where = (
            f"{secret.secret} lue à l'étape {secret.step} ({secret.tool} {secret.args})"
            if secret
            else f"étape {step.n} ({step.tool})"
        )
        return summary, where
    return (
        f"L'agent s'écarte de sa tâche « {run.task} » : il a tenté {action} ({facts}).",
        f"étape {step.n} ({step.tool})",
    )


def _guide_incidents(incident: Incident, run: Run, step: Step) -> list[GuideIncident]:
    legs = [name for name in LEGS if getattr(incident.legs, name).confirmed]
    if not legs:
        summary = (
            f"Action irréversible hors mandat : {step.tool} {step.args} "
            f"({incident.reason}). Tâche : « {run.task} »."
        )
        gi = GuideIncident(
            id=f"{incident.id}-rationalization",
            leg="rationalization",
            owner_role="soc",
            summary=summary,
            source=f"étape {step.n} ({step.tool})",
        )
        return [gi]
    out = []
    for name in legs:
        summary, source = _root_cause(name, incident, run, step)
        out.append(
            GuideIncident(
                id=f"{incident.id}-{name}",
                leg=name,
                owner_role=OWNERS[name],
                summary=summary,
                source=source,
            )
        )
    return out


class Incidents:
    def __init__(
        self, runs: Runs, make_guide: Callable[[GuideIncident], Guide]
    ) -> None:
        self.runs, self.make_guide = runs, make_guide
        self._incidents: dict[str, Incident] = {}
        self._tasks: set[asyncio.Task[None]] = (
            set()
        )  # the loop only keeps weak references

    def open(
        self, run: Run, step: Step, severity: Literal["critique", "haute"]
    ) -> Incident:
        assert step.legs is not None and step.reason is not None  # set by Guard first
        incident = Incident(
            id=uuid.uuid4().hex[:12],
            run_id=run.id,
            step=step.n,
            severity=severity,
            reason=step.reason,
            created_at=datetime.now(UTC).isoformat(),
            decision=step.status,
            sources=sources(run, step),
            legs=step.legs,
            guides=[],
        )
        planned = _guide_incidents(incident, run, step)
        incident.guides = [
            OwnerGuide(leg=g.leg, owner_role=g.owner_role) for g in planned
        ]
        self._incidents[incident.id] = incident
        self.runs.log.append(
            "incident",
            {"run": run.id, "n": step.n, "incident": incident.id, "severity": severity},
        )
        for gi, owner in zip(planned, incident.guides, strict=True):
            task = asyncio.get_running_loop().create_task(self._write(gi, owner))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return incident

    async def _write(self, gi: GuideIncident, owner: OwnerGuide) -> None:
        try:
            guide = await asyncio.to_thread(self.make_guide, gi)
        except Exception:
            log.exception("guide %s failed", gi.id)
            owner.status = "unavailable"
            return
        owner.status, owner.guide_id = guide.status, guide.id

    def _shown(self, incident: Incident) -> Incident:
        run = self.runs.get(incident.run_id)
        assert run is not None
        return incident.model_copy(
            update={"decision": run.steps[incident.step - 1].status}
        )

    def get(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        return self._shown(incident) if incident else None

    def all(self) -> list[Incident]:
        queue = sorted(
            self._incidents.values(), key=lambda i: (ORDER[i.severity], i.created_at)
        )
        return [self._shown(i) for i in queue]
