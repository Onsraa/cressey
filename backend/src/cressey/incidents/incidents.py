"""One incident per held call: where its values came from, the legs that confirm it, and
a fix guide for each leg's owner. The sources are traced, then the guides written, in the
background once the call is held."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from typing import Literal

from cressey.domain.guides import Guide, GuideIncident
from cressey.domain.incidents import (
    Fix,
    FleetSignal,
    Incident,
    OwnerGuide,
    Replay,
    Source,
)
from cressey.domain.owners import LEGS, OWNERS, LegName
from cressey.domain.policy import Fleet
from cressey.domain.reasons import Reason, Target, target
from cressey.domain.runs import Mandate, Preflight, Run, Step
from cressey.engine.agent_text import TASK_WAY_OUT
from cressey.incidents.fixes import fixes_for
from cressey.incidents.fleet import FleetWatch
from cressey.scan.secrets import redact
from cressey.scan.trace import Reads, strings, trace
from cressey.store.runs import Runs
from cressey.tasks import Tasks

log = logging.getLogger(__name__)
ORDER = {"critique": 0, "haute": 1}
# The task and its mandate assessed for the triangle's risk factors (engine/preflight.py).
AssessTask = Callable[[str, Mandate], Awaitable[Preflight | None]]


def sources(
    call: str, earlier: list[Step], reads: Reads, known: Mapping[str, str]
) -> list[Source]:
    found = []
    for origin in trace(call, reads):
        read = earlier[origin.step - 1]
        fingerprint = known.get(origin.token)
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
                value=redact(origin.token, known) if shown else f"[{origin.how}]",
            )
        )
    return found


def source_trace(
    run: Run, step: Step, hidden: Mapping[str, str]
) -> Callable[[], list[Source]]:
    """Where each value of the held call was first read, ready to run in a thread. The
    results and arguments it reads are copied now, on the loop: a run that ends drops them.
    The sources hide what the call was hidden with (`hidden`, value -> fingerprint)."""
    earlier = run.steps[: step.n - 1]
    reads = [(s.n, s.result) for s in earlier if s.result]
    call = " ".join(strings(step.raw_args))
    return partial(sources, call, earlier, reads, dict(hidden))


def _root_cause(
    name: LegName, incident: Incident, run: Run, step: Step
) -> tuple[str, str]:
    """(summary, source) for one leg's guide: a sentence built by code from the facts."""
    facts = " ; ".join(getattr(incident.legs, name).facts)
    action = f"{step.tool} {step.args}"
    secret = next((s for s in incident.sources if s.secret), None)
    if name == "pressure":
        summary = (
            f"The task pushes the agent: {facts}. It then tried an action outside the "
            f"mandate ({action}). Task: “{run.task}”."
        )
        return summary, "task"
    if name == "opportunity":
        used = f"It used it in {action}." if secret else f"Action held: {action}."
        summary = f"A secret the task doesn't need was within the agent's reach: {facts}. {used}"
        where = (
            f"{secret.secret} read at step {secret.step} ({secret.tool} {secret.args})"
            if secret
            else f"step {step.n} ({step.tool})"
        )
        return summary, where
    return (
        f"The agent strays from its task “{run.task}”: it tried {action} ({facts}).",
        f"step {step.n} ({step.tool})",
    )


def _guide_incidents(incident: Incident, run: Run, step: Step) -> list[GuideIncident]:
    legs = [name for name in LEGS if getattr(incident.legs, name).confirmed]
    if not legs:
        summary = (
            f"Irreversible action outside the mandate: {step.tool} {step.args} "
            f"({incident.reason}). Task: “{run.task}”."
        )
        gi = GuideIncident(
            id=f"{incident.id}-rationalization",
            leg="rationalization",
            owner_role="soc",
            summary=summary,
            source=f"step {step.n} ({step.tool})",
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
        self,
        runs: Runs,
        make_guide: Callable[[GuideIncident], Guide],
        fleet: Fleet | None = None,
        assess_task: AssessTask | None = None,
    ) -> None:
        self.runs, self.make_guide = runs, make_guide
        self.assess_task = assess_task
        self.fleet_watch = FleetWatch(fleet or Fleet(), runs.log)
        self.clock: Callable[[], datetime] = lambda: datetime.now(UTC)
        self._incidents: dict[str, Incident] = {}
        self._tasks: Tasks[None] = Tasks()  # the guides and the fixed task's assessment
        # The source trace of each incident, under its number: one step may open several.
        self._traces: Tasks[None] = Tasks()

    def open(
        self,
        run: Run,
        step: Step,
        severity: Literal["critique", "haute"],
        hidden: Mapping[str, str],
    ) -> Incident:
        assert (
            step.legs is not None and step.reason is not None
        )  # set by the engine first
        incident = Incident(
            id=uuid.uuid4().hex[:12],
            run_id=run.id,
            step=step.n,
            severity=severity,
            reason=step.reason,
            reasons=step.reasons,
            created_at=self.clock().isoformat(),
            decision=step.status,
            sources=[],  # traced after this returns
            tracing=True,
            legs=step.legs,
            guides=[],
        )
        # Who gets a guide is known now; what each is told waits for the trace.
        planned = _guide_incidents(incident, run, step)
        incident.guides = [
            OwnerGuide(leg=g.leg, owner_role=g.owner_role) for g in planned
        ]
        incident.fixes = fixes_for(incident, run)
        self._incidents[incident.id] = incident
        if severity == "critique":
            self._count(run, step)
        self.runs.log.append(
            "incident",
            {"run": run.id, "n": step.n, "incident": incident.id, "severity": severity},
        )
        way_out = next((f for f in incident.fixes if f.leg == "pressure"), None)
        # The fixed task assessed: the before and after, without a new run.
        if way_out and self.assess_task and run.kind != "replay":
            fixed = self.assess_task(f"{run.task} {TASK_WAY_OUT}", run.mandate)
            self._tasks.spawn(self._assessed(way_out, fixed))
        # The trace takes seconds on a big call: in the background and off the event loop, so
        # the decision, which depends on all the above, doesn't wait for it.
        snapshot = source_trace(run, step, hidden)
        self._traces.once(
            (run.id, len(self._incidents)),
            lambda: self._traced(incident, run, step, snapshot),
        )
        return incident

    async def _traced(
        self,
        incident: Incident,
        run: Run,
        step: Step,
        snapshot: Callable[[], list[Source]],
    ) -> None:
        """The incident's sources, then its guides: they name where the secret was read."""
        try:
            incident.sources = await asyncio.to_thread(snapshot)
        except Exception:  # a background task has no caller to raise to: report it
            log.exception("source trace of incident %s failed", incident.id)
        incident.tracing = False
        planned = _guide_incidents(incident, run, step)
        for gi, owner in zip(planned, incident.guides, strict=True):
            self._tasks.spawn(self._write(gi, owner))

    async def settled(self, run_id: str) -> None:
        """Every source trace of this run's incidents has ended."""
        await self._traces.settled(run_id)

    async def _assessed(self, fix: Fix, fixed: Awaitable[Preflight | None]) -> None:
        fix.preflight = await fixed

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
        self.fleet_watch.count(
            target(step.tool, step.reasons),
            f"{step.tool} | {step.reason}",
            [r.check for r in step.reasons],
            run.id,
            self.clock(),
        )

    def has(self, run_id: str, reasons: Sequence[Reason]) -> bool:
        """Has this run an incident for these checks on these targets?"""
        keys = [r.key for r in reasons]
        return any(
            i.run_id == run_id and [r.key for r in i.reasons] == keys
            for i in self._incidents.values()
        )

    def signalled(self, target: Target) -> bool:
        """Has a fleet signal gone up for this target (the tool and the floor's reason)?"""
        return self.fleet_watch.signalled(target)

    def fleet(self) -> list[FleetSignal]:
        """The signals across runs, the latest first."""
        return self.fleet_watch.signals()

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

    def replayed(self, incident_id: str, result: Replay) -> None:
        """The last « Rejouer ×5 » of this incident (replay/), kept on it and logged."""
        self._incidents[incident_id].replay = result
        self.runs.log.append(
            "replay", {"incident": incident_id, "passed": result.passed}
        )

    def get(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        return self._shown(incident) if incident else None

    def all(self) -> list[Incident]:
        queue = sorted(
            self._incidents.values(), key=lambda i: (ORDER[i.severity], i.created_at)
        )
        return [self._shown(i) for i in queue]
