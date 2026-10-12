"""Cressey's decision on every agent call, whatever way it came in (the MCP gateway, a Claude
Code hook). Before it runs: the safety floor, the tripwires, Jev's floor labels and the
triangle, then the response the policy gives. Once it ran: the secret scan and the ledger.
It knows nothing of MCP, hooks or HTTP: an adapter turns its events into `before` and
`after`, and a `Refused` into the answer the agent sees."""

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from typing import Literal, Protocol

from cressey.domain.acts import Act, Asker
from cressey.domain.incidents import Incident
from cressey.domain.policy import Policy, Response, ToolRule
from cressey.domain.reasons import Reason, Target, joined, target
from cressey.domain.runs import Legs, Run, Shadow, Step
from cressey.engine.agent_text import (
    REFUSED,
    SUSPENDED,
    WAY_OUT,
    Drafter,
    check_message,
    fallback,
    finish,
    held,
    stop_sentence,
)
from cressey.engine.case.case import CaseReader, closing_excuse, excuse_reason
from cressey.engine.floor.labels import ask_tool_kind, floor_labels, tool_kind
from cressey.engine.floor.rules import check, edits_a_file
from cressey.engine.floor.tripwires import at_cressey, trap
from cressey.engine.ledger import Ledger
from cressey.engine.provenance import asked_by
from cressey.engine.reading import read_before
from cressey.engine.triangle import alarm, alarm_reason, legs, read_after, read_only
from cressey.judge import Judge, NotRecorded, yes
from cressey.scan.secrets import fingerprint, redact, scan
from cressey.store.runs import Runs
from cressey.tasks import Tasks

log = logging.getLogger(__name__)

# Jev's floor labels and the triangle can fire on one call: the strictest response applies,
# so a check on alert never lifts another one's hold.
STRICTNESS: tuple[Response, ...] = ("alert", "review", "stop")


class Refused(Exception):
    """The call may not run, or was held and not approved: the text is what the agent reads."""


class IncidentDesk(Protocol):
    """Where the engine opens an incident for a call it holds or alerts on (incidents/)."""

    def open(
        self, run: Run, step: Step, severity: Literal["critique", "haute"]
    ) -> Incident: ...

    def has(self, run_id: str, reasons: Sequence[Reason]) -> bool:
        """Has this run an incident for these checks on these targets?"""
        ...

    def signalled(self, target: Target) -> bool:
        """Has a fleet signal gone up for this target?"""
        ...


def act_on_pressure(runs: Runs, run: Run, step: Step, legs: Legs) -> None:
    """Without a human, once each: pressure sends the way out with this call's result;
    pressure and opportunity drop the key to read-only for destructive calls."""
    if legs.pressure.confirmed and run.way_out_step is None:
        run.way_out_step = step.n
        runs.log_step(run, step, "way_out")
    if read_only(legs) and run.read_only_step is None:
        run.read_only_step = step.n
        runs.log_step(run, step, "read_only")


def _ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000


class Engine:
    def __init__(
        self,
        runs: Runs,
        incidents: IncidentDesk,
        policy: Policy,
        judge: Judge,
        hold_timeout: float,
        triangle_holds: bool = True,
        holds: Literal["wait", "refuse"] = "wait",
        drafter: Drafter | None = None,
        thought_holds: bool = False,
        origins: frozenset[tuple[str, int]] = frozenset(),
    ) -> None:
        self.runs, self.incidents = runs, incidents
        self.thought_holds = thought_holds
        self.origins = origins  # where Cressey answers: no call may aim there
        self.policy, self.judge, self.hold_timeout = policy, judge, hold_timeout
        self.ledger = Ledger(judge)
        self.case = CaseReader(judge, policy.triangle)
        self.triangle_holds, self.holds, self.drafter = triangle_holds, holds, drafter
        self.drafts: Tasks[None] = Tasks()  # the drafter's, while a call is held
        self._late: Tasks[None] = Tasks()  # the reads of calls too long to read first
        self._ending: Tasks[None] = (
            Tasks()
        )  # ended runs, waiting for their reads to end
        self._kinds: dict[str, ToolRule] = {}  # Jev's labels, per tool name

    def _response(
        self,
        tool: str,
        reasons: list[Reason],
        trapped: bool,
        floor: bool,
        labelled: list[Response],
        triangle: bool,
        only_reads: bool,
    ) -> Response | None:
        """What the policy does with a call a check fired on, or None when none did:
        `labelled` holds the responses of Jev's floor labels that fired, and `triangle` says
        whether the triangle did."""
        if not reasons:
            return None
        r = self.policy.responses
        if trapped:
            response = r.trap_key_read if only_reads else r.trap_key
        elif floor:
            response = r.floor
        else:
            fired = [*labelled, *([r.triangle] if triangle else [])]
            response = max(fired, key=STRICTNESS.index)
        if r.fleet == "stop" and self.incidents.signalled(target(tool, reasons)):
            response = "stop"  # many runs after one target: no human queue for them all
        if response == "review" and self.holds == "refuse":
            response = "stop"  # CRESSEY_HOLDS=refuse: nobody waits for a human
        return response

    async def _rule(self, name: str) -> ToolRule | None:
        """The policy's rule for a tool, else the kind Jev labels from its name, asked once
        per tool. None while Jev can't answer: the floor then holds the call as a tool not in
        the policy."""
        rule = self.policy.tools.get(name) or self._kinds.get(name)
        if rule is not None:
            return rule
        try:
            answer = await ask_tool_kind(self.judge, name)
        except NotRecorded:
            return None
        kind = None if answer is None else tool_kind(answer, self.policy.floor.read)
        if kind is None:
            return None
        self._kinds[name] = rule = ToolRule(kind=kind)
        log.info("%s: not in the policy, labelled %s by the decision model", name, kind)
        return rule

    async def _labelled(
        self, run: Run, step: Step, rule: ToolRule | None, floor: list[Reason]
    ) -> list[tuple[Reason, Response]]:
        """Why Jev holds a write that code let through, each reason with its response: it
        can't be undone beyond the mandate, or it changes production (unless that check is
        off). They only add holds; a call code holds or classes otherwise isn't asked, nor
        one too long to read before it runs. With no answer, a write code can't vouch for
        waits for a human: only a file edit, whose path code checked, goes on."""
        if floor or step.risk != "write" or not read_before(step):
            return []
        try:
            labels = await floor_labels(run, step, self.judge, self.policy.triangle)
        except NotRecorded:  # a replay miss: not asked, as on the run that was recorded
            return []
        f, r = self.policy.floor, self.policy.responses
        if labels is None:
            no_answer = Reason(check="no_answer")
            return [] if edits_a_file(rule) else [(no_answer, r.irreversible)]
        fired: list[tuple[Reason, Response]] = []
        if (p := yes(labels["irreversible"])) >= f.irreversible:
            fired.append((Reason(check="irreversible", score=p), r.irreversible))
        production = r.production
        if production != "off" and (p := yes(labels["production"])) >= f.production:
            fired.append((Reason(check="production", score=p), production))
        return fired

    async def before(self, run: Run, act: Act) -> Step:
        """Cressey's decision on an act before it runs: its step, let through or approved.
        Raises Refused when the act is refused, or held and not approved."""
        start = time.perf_counter()
        name, args = act.tool, act.args
        rule = await self._rule(name)
        risk, guarded = check(rule, args, run.mandate)
        trapped = trap(args, self.policy.decoys)
        aimed = at_cressey(rule, args, self.origins)
        floor = [r for r in (trapped, aimed, guarded) if r is not None]
        # A trap key softens only a read the floor lets through: a guarded one is still held.
        only_reads = trapped is not None and risk == "read" and not (guarded or aimed)
        # Off the event loop, like the result scan: a large argument takes a while to redact.
        # A copy of the secrets known so far, which other calls may add to meanwhile, and the
        # trap keys: one the agent got outside Cressey must not show in clear either.
        dumped = json.dumps(args, ensure_ascii=False)
        known = dict(run.known) | {
            v: fingerprint(v) for v in self.policy.decoys.values()
        }

        def prepare() -> tuple[str, list[Asker]]:
            return redact(dumped, known), asked_by(run, args)

        shown, asked = await asyncio.to_thread(prepare)
        step = self.runs.add_step(run, act, shown, risk, floor, asked)
        try:
            if run.revoked:
                self.runs.mark(run, step, "denied")
                raise Refused(SUSPENDED)
            # Side by side: the floor's label waits for no more than the triangle already does,
            # and with thought holds on, the agent's words before the call are read meanwhile.
            triangle, labelled, _ = await asyncio.gather(
                legs(run, step, self.ledger, self.policy.triangle),
                self._labelled(run, step, rule, floor),
                self._read_words(run, step),
            )
            if run.revoked:  # a parallel call was held while this one was being judged
                self.runs.mark(run, step, "denied")
                raise Refused(SUSPENDED)
            triangle_hold = self.triangle_holds and alarm(triangle, risk)
            excuse = closing_excuse(run, triangle) if self.thought_holds else None
            labels = [why for why, _ in labelled]
            reasons = (
                floor
                or labels
                or ([excuse_reason(run, excuse)] if excuse is not None else [])
                or ([alarm_reason(triangle)] if triangle_hold else [])
            )
            if excuse is not None and not (floor or labels):
                # The stop is the words', shown on the thought; their excuse confirms the leg.
                step.stopped_by = excuse
                said, leg = run.case.events[excuse], triangle.rationalization
                leg.confirmed, leg.score = True, max(leg.score, said.p)
                leg.facts.append(
                    f"excuse in the agent's words, {said.p:.2f}: “{said.quote}”"
                )
            self.runs.score(run, step, triangle, reasons)
            self._shadow_later(run, step, joined(floor))
            # The Observateur run and the floor-alone ablation show what happens without it.
            if self.triangle_holds and run.kind != "control":
                act_on_pressure(self.runs, run, step, triangle)
            # A trap key used again only to read opens no second incident: one per key.
            if (
                reasons
                and run.kind != "replay"
                and not (only_reads and self.incidents.has(run.id, reasons))
            ):
                self.incidents.open(run, step, "critique" if floor else "haute")
            step.check_ms = _ms_since(start)  # the time to stop, when the call is held
            # A call that would be held still goes to a human: only the others are refused.
            if not reasons and run.read_only_step and risk == "destructive":
                step.because([Reason(check="read_only")])
                self.runs.mark(run, step, "denied")
                raise Refused(REFUSED)
            # The agent learns it was held, never why: a reason teaches it what to route around
            # (Baker et al. 2025) and would name a trap key. The reason stays with the humans.
            held_error = Refused(held())
            response = self._response(
                name,
                reasons,
                bool(trapped),
                bool(floor),
                [r for _, r in labelled],
                excuse is not None or triangle_hold,
                only_reads,
            )
            if response == "alert":
                self.runs.mark(run, step, "alerted")  # through, with its incident open
            elif reasons and run.kind != "live":
                self.runs.mark(run, step, "would_hold")
                if run.kind == "replay":
                    raise held_error
            elif response == "stop":
                run.revoked = True  # the rest of the run is denied
                self.runs.mark(run, step, "denied")
                raise Refused(REFUSED)
            elif reasons:
                self._draft(run, step)
                stop_after = self.policy.stuck.rejections
                if not await self.runs.hold(run, step, self.hold_timeout, stop_after):
                    told = held(step.message)
                    if run.stopped:
                        told = f"{told} {stop_sentence(stop_after)}"
                    raise Refused(told)
            return step
        except BaseException:
            step.running = False  # refused: no result will come
            raise

    async def _read_words(self, run: Run, step: Step) -> None:
        if self.thought_holds:
            await self.case.read_until(run, step)

    def _shadow_later(self, run: Run, step: Step, floor: str | None) -> None:
        """What the case would decide for this call, beside today's decision and after it:
        in the background, never awaited, so the call's latency and hold are unchanged."""
        task = self.case.shadow_soon(run, step, floor)
        if task is not None:
            task.add_done_callback(lambda t: self._shadowed(run, step, t))

    def _shadowed(self, run: Run, step: Step, task: asyncio.Task[Shadow]) -> None:
        if task.cancelled():  # the server is stopping
            return
        failure = task.exception()
        if failure is not None:  # a background task has no caller to raise to
            log.error(
                "shadow of step %d of run %s failed", step.n, run.id, exc_info=failure
            )
            return
        self.runs.set_shadow(run, step, task.result())

    async def after(
        self, run: Run, step: Step, is_error: bool, text: str, label: bool = True
    ) -> str | None:
        """What the call returned, read: the secret scan, the ledger, and the triangle on a
        call too long to read before it ran. Without `label`, the caller reads the step
        later, once the agent's words are in. The way out, when this call carries it."""
        scanned = time.perf_counter()
        found = await asyncio.to_thread(scan, text)
        step.scan_ms = _ms_since(scanned)
        self.runs.record(run, step, is_error, text, found)
        if label:
            # Read now: the next write won't wait for it.
            self.ledger.label_soon(run, step.n - 1)
        # Too long to read before it ran: read now, without holding the developer's work.
        late = step.reason is None and step.risk != "read" and not read_before(step)
        if late and run.kind != "replay":
            self._late.once((run.id, step.n), lambda: self._read_late(run, step))
        return WAY_OUT if run.way_out_step == step.n else None

    def ended(self, run: Run) -> None:
        """The run ended (its report, its session's end): what its calls returned is dropped
        once every read of its steps is done, so a long-lived Cressey keeps what it decided,
        not all its agents read. A session resumed meanwhile keeps it all."""
        self._ending.spawn(self._forget_results(run, list(run.steps)))

    async def _forget_results(self, run: Run, steps: list[Step]) -> None:
        # The shadows and late reads may still ask the ledger for labels: they settle first.
        await self.case.settled(run)
        await self._late.settled(run.id)
        await self.ledger.settled(run)
        if run.ended_at is not None:
            self.runs.forget_results(steps)

    def _draft(self, run: Run, step: Step) -> None:
        """What the human can send if they reject this hold: the fallback at once, then a
        model's draft, if one comes in time and passes the check."""
        step.draft = fallback(run.mandate)
        if self.drafter is not None:
            self.drafts.spawn(self._draft_late(self.drafter, run, step))

    async def _draft_late(self, drafter: Drafter, run: Run, step: Step) -> None:
        # The model reads the task, the mandate, the tool and the risk class: nothing else.
        asking = asyncio.to_thread(
            drafter.draft, run.task, run.mandate, step.tool, step.risk
        )
        try:
            draft = finish(await asyncio.wait_for(asking, self.hold_timeout))
        except Exception:  # a background task has no caller to raise to: report it
            log.exception("draft for step %d of run %s failed", step.n, run.id)
            return
        # Checked now, not when the hold began: the run may have seen more secrets since.
        if check_message(draft, run, self.policy.decoys) is None:
            step.draft = draft

    async def _read_late(self, run: Run, step: Step) -> None:
        """A call that ran before it could be read: if the triangle would have held it,
        it alerts now, with its incident open."""
        try:
            late = await read_after(run, step, self.ledger, self.policy.triangle)
        except Exception:  # a background task has no caller to raise to: report it
            log.exception("late read of step %d of run %s failed", step.n, run.id)
            return
        alarmed = self.triangle_holds and alarm(late, step.risk)
        reasons = (
            [alarm_reason(late).model_copy(update={"afterwards": True})]
            if alarmed
            else []
        )
        # Alarm or not, the step shows what the late read found, an unanswered model too.
        self.runs.score(run, step, late, reasons)
        if not alarmed:
            return
        self.runs.mark(run, step, "alerted")
        self.incidents.open(run, step, "haute")
