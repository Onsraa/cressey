"""One incident per held call: where its values came from, the legs that confirm it, and
a fix guide for each leg's owner, written in the background as soon as the call is held."""

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from cressey.core.models import (
    Fix,
    Fleet,
    FleetSignal,
    Incident,
    OwnerGuide,
    Replay,
    Run,
    Source,
    Step,
)
from cressey.core.runs import Runs
from cressey.core.secret_scan import redact
from cressey.core.trace import strings, trace
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
# Plays the incident's variants again with these fixes, for this task: « Rejouer ×5 ».
Replayer = Callable[[list[Fix], str], Coroutine[Any, Any, Replay]]
# The task author's fix: the way out, written into the task itself.
TASK_WAY_OUT = (
    "Si la tâche ne peut pas se faire sans sortir du mandat, déclare-la impossible : "
    "c'est une réponse acceptée."
)


def sources(run: Run, step: Step) -> list[Source]:
    earlier = run.steps[: step.n - 1]
    reads = [(s.n, s.result) for s in earlier if s.result]
    found = []
    for origin in trace(" ".join(strings(step.raw_args)), reads):
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


def _fixes(incident: Incident, run: Run) -> list[Fix]:
    """What Cressey can change itself for each confirmed leg, once a human approves it.
    Rationalization gets none: its owner's guide is the fix."""
    fixes = []
    if incident.legs.pressure.confirmed:
        fixes.append(
            Fix(
                leg="pressure",
                owner_role=OWNERS["pressure"],
                text=f"Ajouter à la tâche : « {TASK_WAY_OUT} »",
                add_to_task=TASK_WAY_OUT,
            )
        )
    reads = [s for s in run.steps[: incident.step - 1] if s.secrets]
    if incident.legs.opportunity.confirmed and reads:
        files = [str(s.raw_args["path"]) for s in reads if "path" in s.raw_args]
        names = ", ".join(sorted({x.name or x.kind for s in reads for x in s.secrets}))
        where = ", ".join(files) or ", ".join(f"étape {s.n} ({s.tool})" for s in reads)
        fixes.append(
            Fix(
                leg="opportunity",
                owner_role=OWNERS["opportunity"],
                text=f"Sortir {names} de l'espace de travail de l'agent ({where}) et lui "
                "donner une clé limitée à sa tâche.",
                move_out=files,
            )
        )
    return fixes


class Incidents:
    def __init__(
        self,
        runs: Runs,
        make_guide: Callable[[GuideIncident], Guide],
        replayer: Replayer | None = None,
        fleet: Fleet | None = None,
    ) -> None:
        self.runs, self.make_guide, self.replayer = runs, make_guide, replayer
        self.fleet_rule = fleet or Fleet()
        self.clock: Callable[[], datetime] = lambda: datetime.now(UTC)
        self._targets: dict[
            str, list[tuple[datetime, str]]
        ] = {}  # target -> (when, run)
        self._signals: dict[str, FleetSignal] = {}
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
            created_at=self.clock().isoformat(),
            decision=step.status,
            sources=sources(run, step),
            legs=step.legs,
            guides=[],
        )
        planned = _guide_incidents(incident, run, step)
        incident.guides = [
            OwnerGuide(leg=g.leg, owner_role=g.owner_role) for g in planned
        ]
        incident.fixes = _fixes(incident, run)
        self._incidents[incident.id] = incident
        if severity == "critique":
            self._count(run, step)
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

    def _count(self, run: Run, step: Step) -> None:
        """Hugging Face / METR: each run alone looks like one hold; many runs held for the same
        target outside their mandate, within a window, are the alarm (« peers doing it »)."""
        now, rule = self.clock(), self.fleet_rule
        target = f"{step.tool} | {step.reason}"
        window = timedelta(minutes=rule.window_minutes)
        seen = [(t, r) for t, r in self._targets.get(target, []) if now - t <= window]
        seen.append((now, run.id))
        self._targets[target] = seen
        ids = list(dict.fromkeys(r for _, r in seen))
        if len(ids) < rule.runs:
            return
        if target not in self._signals:
            self.runs.log.append("fleet_signal", {"target": target, "runs": len(ids)})
        self._signals[target] = FleetSignal(
            target=target,
            runs=ids,
            first_at=seen[0][0].isoformat(),
            last_at=now.isoformat(),
        )

    def fleet(self) -> list[FleetSignal]:
        """The signals across runs, the latest first."""
        return sorted(self._signals.values(), key=lambda s: s.last_at, reverse=True)

    def approve(self, incident_id: str, leg: LegName) -> bool:
        """A human approves the fix proposed for this leg."""
        incident = self._incidents.get(incident_id)
        fix = (
            next((f for f in incident.fixes if f.leg == leg), None)
            if incident
            else None
        )
        if fix is None:
            return False
        fix.approved = True
        self.runs.log.append("fix_approved", {"incident": incident_id, "leg": leg})
        return True

    async def replay(self, incident_id: str) -> Replay | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        replayer, run = self.replayer, self.runs.get(incident.run_id)
        assert replayer is not None and run is not None  # create_app sets the replayer
        fixes, task = incident.fixes, run.task
        # Every replayed session runs its own server: off this loop, so the API keeps serving.
        result = await asyncio.to_thread(lambda: asyncio.run(replayer(fixes, task)))
        incident.replay = result
        self.runs.log.append(
            "replay", {"incident": incident_id, "passed": result.passed}
        )
        return result

    def get(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        return self._shown(incident) if incident else None

    def all(self) -> list[Incident]:
        queue = sorted(
            self._incidents.values(), key=lambda i: (ORDER[i.severity], i.created_at)
        )
        return [self._shown(i) for i in queue]
