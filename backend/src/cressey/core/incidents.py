"""One incident per held call: where its values came from, the legs that confirm it, and
a fix guide for each leg's owner, written in the background as soon as the call is held."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

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
from cressey.domain.runs import Mandate, Preflight, Run, Step
from cressey.scan.secrets import redact
from cressey.scan.trace import strings, trace
from cressey.store.runs import Runs

log = logging.getLogger(__name__)
ORDER = {"critique": 0, "haute": 1}
# Plays the incident's variants again with these fixes, for this task: « Replay ×5 ».
Replayer = Callable[[list[Fix], str], Coroutine[Any, Any, Replay]]
# The task and its mandate assessed for the triangle's risk factors (core/preflight.py).
AssessTask = Callable[[str, Mandate], Awaitable[Preflight | None]]
# The task author's fix: the way out, written into the task itself.
TASK_WAY_OUT = (
    "If the task can't be done without leaving the mandate, declare it impossible: "
    "that is an accepted answer."
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


def _fixes(incident: Incident, run: Run) -> list[Fix]:
    """What Cressey can change itself for each confirmed leg, once a human approves it.
    Rationalization gets none: its owner's guide is the fix."""
    fixes = []
    if incident.legs.pressure.confirmed:
        fixes.append(
            Fix(
                leg="pressure",
                owner_role=OWNERS["pressure"],
                text=f"Add to the task: “{TASK_WAY_OUT}”",
                add_to_task=TASK_WAY_OUT,
            )
        )
    reads = [s for s in run.steps[: incident.step - 1] if s.secrets]
    if incident.legs.opportunity.confirmed and reads:
        files = [str(s.raw_args["path"]) for s in reads if "path" in s.raw_args]
        names = ", ".join(sorted({x.name or x.kind for s in reads for x in s.secrets}))
        where = ", ".join(files) or ", ".join(f"step {s.n} ({s.tool})" for s in reads)
        fixes.append(
            Fix(
                leg="opportunity",
                owner_role=OWNERS["opportunity"],
                text=f"Move {names} out of the agent's workspace ({where}) and give it "
                "a key limited to its task.",
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
        assess_task: AssessTask | None = None,
    ) -> None:
        self.runs, self.make_guide, self.replayer = runs, make_guide, replayer
        self.assess_task = assess_task
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
        way_out = next((f for f in incident.fixes if f.leg == "pressure"), None)
        # The fixed task assessed: the before and after, without a new run.
        if way_out and self.assess_task and run.kind != "replay":
            fixed = self.assess_task(f"{run.task} {TASK_WAY_OUT}", run.mandate)
            task = asyncio.get_running_loop().create_task(
                self._assessed(way_out, fixed)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return incident

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

    def has(self, run_id: str, reason: str) -> bool:
        """Has this run an incident with this reason?"""
        return any(
            i.run_id == run_id and i.reason == reason for i in self._incidents.values()
        )

    def signalled(self, target: str) -> bool:
        """Has a fleet signal gone up for this target (the tool and the floor's reason)?"""
        return target in self._signals

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
