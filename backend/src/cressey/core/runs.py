"""Runs in memory: the key Cressey issued for each one, its steps, and the holds
waiting for a human."""

import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
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
    Step,
)
from cressey.core.secret_scan import Secret, redact
from cressey.core.triangle import confirmed, read_only


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class Runs:
    def __init__(self, log: EventLog) -> None:
        self.log = log
        self._runs: dict[str, Run] = {}
        self._keys: dict[str, str] = {}  # sha256 of the key -> run id
        self._waiting: dict[tuple[str, int], asyncio.Future[bool]] = {}

    def create(self, spec: RunIn) -> RunCreated:
        run = Run(
            id=uuid.uuid4().hex[:12],
            task=spec.task,
            mandate=spec.mandate,
            visibility=spec.visibility,
            kind=spec.kind,
            started_at=_now().isoformat(),
        )
        key = "csy_" + secrets.token_urlsafe(24)
        self._runs[run.id] = run
        self._keys[_digest(key)] = run.id
        self.log.append("run", {"run": run.id, "task": run.task})
        return RunCreated(id=run.id, key=key)

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
        )
        run.steps.append(step)
        self._log(run, step, "call", tool=tool, args=shown, risk=risk, reason=reason)
        return step

    def score(self, run: Run, step: Step, legs: Legs, reason: str | None) -> None:
        step.legs, step.reason = legs, reason
        legs_confirmed: list[JsonValue] = list(confirmed(legs))
        self._log(run, step, "legs", confirmed=legs_confirmed, reason=reason)

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
        self.log.append("message", {"run": run.id, **message.model_dump()})

    def end(self, run: Run, report: str) -> None:
        run.report, run.ended_at = redact(report, run.known), _now().isoformat()
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
        step.is_error, step.result = is_error, text
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

    async def hold(self, run: Run, step: Step, timeout: float) -> bool:
        """Wait for a human decision; True when this call is approved. The run's key stays
        revoked while any of its calls is held, rejected or expired: with parallel calls,
        one approval must not free a key another hold still needs."""
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
        blocking = ("held", "rejected", "expired")
        others = [s for s in run.steps if s is not step]
        run.revoked = step.status != "approved" or any(
            s.status in blocking for s in others
        )
        return step.status == "approved"

    def decide(self, run_id: str, n: int, approve: bool) -> bool:
        decision = self._waiting.get((run_id, n))
        if decision is None or decision.done():
            return False
        decision.set_result(approve)
        return True
