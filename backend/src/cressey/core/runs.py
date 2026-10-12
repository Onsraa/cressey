"""Runs in memory: the key Cressey issued for each one, its steps, and the holds
waiting for a human. With a store, each run's spec and key digest are written there and
restored at start, its steps as the event log recorded them."""

import asyncio
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from cressey.core.eventlog import EventLog
from cressey.core.models import (
    Hold,
    Leg,
    Legs,
    Message,
    Risk,
    Run,
    RunCreated,
    RunIn,
    Shadow,
    Step,
)
from cressey.core.secret_scan import Secret, redact
from cressey.core.triangle import confirmed, read_only

# The step field each later event of a step sets, as the log records it.
FROM_LOG = {"status": "status", "legs": "reason", "result": "is_error"}


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _spec(run: Run) -> JsonValue:
    """What a run is registered with: enough to know its key and mandate after a restart."""
    keep = {"id", "task", "mandate", "visibility", "kind", "started_at"}
    return run.model_dump(mode="json", include=keep)


class Runs:
    def __init__(self, log: EventLog, store: Path | None = None) -> None:
        self.log = log
        self.store = store  # one JSON line per run (its spec and key digest) or session
        self._runs: dict[str, Run] = {}
        self._keys: dict[str, str] = {}  # sha256 of the key -> run id
        self._waiting: dict[tuple[str, int], asyncio.Future[bool]] = {}
        # A message being streamed in: (run, message id) -> (its Message, the raw text).
        self._streaming: dict[tuple[str, str], tuple[Message, str]] = {}
        # A later Claude Code session on a run's key: (that run, session id) -> its own run.
        self._sessions: dict[tuple[str, str], str] = {}
        if store is not None and store.exists():
            self._restore(store)

    def _keep(self, entry: dict[str, JsonValue]) -> None:
        if self.store is not None:
            with self.store.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    def _restore(self, store: Path) -> None:
        """The runs a previous start registered: their keys work again. Their steps come back
        as the log recorded them, so numbering goes on; a call that was still held when
        Cressey stopped is logged expired. A restart ends a suspension: what the run had
        in memory (results, secrets read, the case) is gone."""
        with store.open(encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e["kind"] == "session":
                    self._runs[e["id"]].session = e["session"]
                    continue
                run = Run.model_validate(e["run"])
                self._runs[run.id] = run
                if e["kind"] == "run":
                    self._keys[e["digest"]] = run.id
                else:  # a later session's run on that key
                    run.session = e["session"]
                    self._sessions[(e["of"], e["session"])] = run.id
        # Each step as the log last recorded it, in the order its call came in.
        recorded: dict[tuple[str, int], dict[str, JsonValue]] = {}
        for event in self.log.events:
            run_id, n = event.data.get("run"), event.data.get("n")
            if not (isinstance(run_id, str) and run_id in self._runs):
                continue
            if not isinstance(n, int):
                continue
            fields = recorded.setdefault((run_id, n), {"n": n})
            if event.kind == "call":
                fields |= {k: event.data[k] for k in ("tool", "args", "risk", "reason")}
            elif field := FROM_LOG.get(event.kind):
                fields[field] = event.data[field]
        for (run_id, _), fields in recorded.items():
            run = self._runs[run_id]
            step = Step.model_validate(fields)
            run.steps.append(step)
            if step.status == "held":
                step.status = "expired"
                self._log(run, step, "status", status="expired", after="restart")

    def create(self, spec: RunIn) -> RunCreated:
        run = self._new(spec)
        key = "csy_" + secrets.token_urlsafe(24)
        self._keys[_digest(key)] = run.id
        self._keep({"kind": "run", "run": _spec(run), "digest": _digest(key)})
        return RunCreated(id=run.id, key=key)

    def _new(self, spec: RunIn) -> Run:
        run = Run(
            id=uuid.uuid4().hex[:12],
            task=spec.task,
            mandate=spec.mandate,
            visibility=spec.visibility,
            kind=spec.kind,
            started_at=_now().isoformat(),
        )
        self._runs[run.id] = run
        self.log.append("run", {"run": run.id, "task": run.task})
        return run

    def for_session(self, run: Run, session: str) -> Run:
        """The run of one Claude Code session on this run's key. The key's own run takes the
        first session; each later one (after /clear, or from a second window) gets a run of
        its own, with the same task and mandate, so their traces never mix."""
        if run.session in (None, session):
            if run.session is None:
                self._keep({"kind": "session", "id": run.id, "session": session})
            run.session = session
            return run
        pair = (run.id, session)
        if pair not in self._sessions:
            spec = RunIn(
                task=run.task,
                mandate=run.mandate,
                visibility=run.visibility,
                kind=run.kind,
            )
            new = self._new(spec)
            new.session, new.preflight = session, run.preflight
            self._sessions[pair] = new.id
            entry = {"kind": "sub", "run": _spec(new), "of": run.id, "session": session}
            self._keep(entry)
        return self._runs[self._sessions[pair]]

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def by_key(self, key: str) -> Run | None:
        run_id = self._keys.get(_digest(key))
        return self._runs[run_id] if run_id else None

    def all(self) -> list[Run]:
        return list(self._runs.values())

    def add_step(
        self,
        run: Run,
        tool: str,
        raw_args: dict[str, JsonValue],
        shown: str,
        risk: Risk,
        reason: str | None,
    ) -> Step:
        """`shown`: the arguments as JSON, secrets redacted. The proxy redacts them off the
        event loop: a large argument takes a while."""
        step = Step(
            n=len(run.steps) + 1,
            tool=tool,
            args=shown,
            risk=risk,
            reason=reason,
            raw_args=raw_args,
            running=True,
        )
        run.steps.append(step)
        self._log(run, step, "call", tool=tool, args=shown, risk=risk, reason=reason)
        return step

    def score(self, run: Run, step: Step, legs: Legs, reason: str | None) -> None:
        step.legs, step.reason = legs, reason
        legs_confirmed: list[JsonValue] = list(confirmed(legs))
        self._log(run, step, "legs", confirmed=legs_confirmed, reason=reason)

    def set_shadow(self, run: Run, step: Step, s: Shadow) -> None:
        """What the case would have done with this call: stored and logged beside the
        decision taken, which it never changes."""
        step.shadow = s
        uses: list[JsonValue] = list(s.uses)
        self._log(
            run, step, "shadow", decision=s.decision, uses=uses, words_read=s.words_read
        )

    def act_on_pressure(self, run: Run, step: Step, legs: Legs) -> None:
        """Without a human, once each: pressure sends the way out with this call's result;
        pressure and opportunity drop the key to read-only for destructive calls."""
        if legs.pressure.confirmed and run.way_out_step is None:
            run.way_out_step = step.n
            self._log(run, step, "way_out")
        if read_only(legs) and run.read_only_step is None:
            run.read_only_step = step.n
            self._log(run, step, "read_only")

    def mark(
        self, run: Run, step: Step, status: Literal["alerted", "denied", "would_hold"]
    ) -> None:
        step.status = status
        self._log(run, step, "status", status=status)

    def say(self, run: Run, text: str) -> None:
        message = Message(after=len(run.steps), text=redact(text, run.known))
        run.messages.append(message)
        # The log keeps what the agent said, not what the thought reading adds later.
        said = message.model_dump(exclude={"source", "thoughts", "read", "scores"})
        self.log.append("message", {"run": run.id, **said})

    def stream(self, run: Run, message_id: str, delta: str, final: bool) -> None:
        """A streamed slice of the agent's words (Claude Code's MessageDisplay hook). Deltas
        for one message grow one Message in place, placed after the calls made before it, so
        the dashboard shows the reasoning as it is produced and the next call's judgment
        reads it. Logged once, when the message is final."""
        key = (run.id, message_id)
        message, raw = self._streaming.get(
            key, (Message(after=len(run.steps), text=""), "")
        )
        if not raw and message not in run.messages:
            run.messages.append(message)
        raw += delta
        message.text, message.streaming = redact(raw, run.known), not final
        self._streaming[key] = (message, raw)
        if final:
            del self._streaming[key]
            said = message.model_dump(exclude={"source", "thoughts", "read", "scores"})
            self.log.append("message", {"run": run.id, **said})

    def prompt(self, run: Run, text: str) -> Message:
        """The user's prompt (Claude Code's UserPromptSubmit), placed where it was sent, even
        mid-turn, and returned. It closes a message cut short by Esc, which Claude Code
        doesn't report. It starts a new turn: the count of refused calls resets and a
        suspended key unlocks, the user being back, but the key waits while a call is still
        held (see `unlock`)."""
        for key in [k for k in self._streaming if k[0] == run.id]:
            self._streaming.pop(key)[0].streaming = False
        message = Message(
            after=len(run.steps), text=redact(text, run.known), role="user"
        )
        run.messages.append(message)
        run.turn = "working"
        # The log keeps what the user typed, not what the thought reading adds later.
        said = message.model_dump(exclude={"source", "thoughts", "read", "scores"})
        self.log.append("message", {"run": run.id, **said})
        if run.revoked or run.refused:
            self.unlock(run)
        return message

    def unlock(self, run: Run) -> None:
        """Reset the count of refused calls and give the key back, the user being back or
        having chosen to. While a call is still held the key stays suspended: that one is
        decided on the dashboard, and its rejection counts in the new turn."""
        run.refused, run.stopped = 0, False
        held = any(s.status == "held" for s in run.steps)
        run.revoked = held
        self.log.append(
            "unlocked", {"run": run.id, "key": "held" if held else "cleared"}
        )

    def connect(self, run: Run) -> None:
        """A Claude Code session started (or resumed): it waits for a prompt."""
        run.turn, run.ended_at = "waiting", None
        self.log.append("session", {"run": run.id, "state": "started"})

    def answered(self, run: Run, report: str) -> None:
        """A Claude Code turn is over (Stop): its last message is the report, until the next."""
        self.report(run, report)
        run.turn = "waiting"

    def disconnect(self, run: Run) -> None:
        """The Claude Code session ended (SessionEnd): the run ends with it."""
        run.ended_at = _now().isoformat()
        self.log.append("session", {"run": run.id, "state": "ended"})

    def route(self, run: Run, via: Literal["mcp", "hook"]) -> None:
        """How this run reached Cressey, for the Run view's badge. Set once, on its first call."""
        if run.via is None:
            run.via = via
            self.log.append("run", {"run": run.id, "via": via})

    def end(self, run: Run, report: str) -> None:
        self.report(run, report)
        run.ended_at = _now().isoformat()

    def report(self, run: Run, report: str) -> None:
        run.report = redact(report, run.known)
        self.log.append("report", {"run": run.id, "report": run.report})

    def checked(self, run: Run, check: Leg) -> None:
        """The report against the log: a contradicted report flags the run."""
        run.report_check = check
        self.log.append(
            "report_check",
            {"run": run.id, "score": check.score, "contradicted": check.confirmed},
        )

    def record(
        self,
        run: Run,
        step: Step,
        is_error: bool,
        text: str,
        found: list[tuple[str, Secret]],
    ) -> None:
        step.is_error, step.result, step.running = is_error, text, False
        step.secrets = [s for _, s in found]
        run.known |= {value: s.fingerprint for value, s in found}
        fingerprints: list[JsonValue] = [s.fingerprint for s in step.secrets]
        self._log(run, step, "result", is_error=is_error, secrets=fingerprints)

    def _log(self, run: Run, step: Step, kind: str, **data: JsonValue) -> None:
        self.log.append(kind, {"run": run.id, "n": step.n, **data})

    def holds(self) -> list[Hold]:
        return [
            Hold(run_id=r, task=self._runs[r].task, step=self._runs[r].steps[n - 1])
            for r, n in self._waiting
        ]

    async def hold(self, run: Run, step: Step, timeout: float, stop_after: int) -> bool:
        """Wait for a human decision; True when this call is approved. The run's key stays
        revoked while any of its calls is held: with parallel calls, one decision must not
        free a key another hold still needs. A rejected or expired call counts as refused,
        and the run stops, key suspended, once `stop_after` calls were refused in a turn."""
        run.revoked = True
        step.status = "held"
        step.held_until = (_now() + timedelta(seconds=timeout)).isoformat()
        self._log(run, step, "status", status="held")
        key = (run.id, step.n)
        self._waiting[key] = decision = asyncio.get_running_loop().create_future()
        try:
            await asyncio.wait_for(decision, timeout)
        except TimeoutError:
            pass
        finally:
            del self._waiting[key]
            if decision.cancelled():  # timed out, or the agent's client gave up
                step.status = "expired"
            else:
                step.status = "approved" if decision.result() else "rejected"
            step.decided_at = _now().isoformat()
            self._log(run, step, "status", status=step.status)
            # In the finally: a cancelled hold is an expired one, and must not leave the key
            # suspended with nothing held and no stop.
            if step.status != "approved":
                run.refused += 1
                run.stopped = run.refused >= stop_after
            run.revoked = run.stopped or any(s.status == "held" for s in run.steps)
        return step.status == "approved"

    def decide(
        self, run_id: str, n: int, approve: bool, message: str | None = None
    ) -> bool:
        decision = self._waiting.get((run_id, n))
        if decision is None or decision.done():
            return False
        self._runs[run_id].steps[n - 1].message = message  # before the agent reads it
        decision.set_result(approve)
        return True
