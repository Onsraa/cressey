"""Runs in memory: the key Cressey issued for each one, its steps, and the holds
waiting for a human."""

import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from pydantic import JsonValue

from cressey.core.models import Hold, Risk, Run, RunCreated, RunIn, Step


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Runs:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._keys: dict[str, str] = {}  # sha256 of the key -> run id
        self._waiting: dict[tuple[str, int], asyncio.Future[bool]] = {}

    def create(self, spec: RunIn) -> RunCreated:
        run = Run(
            id=uuid.uuid4().hex[:12],
            task=spec.task,
            mandate=spec.mandate,
            started_at=datetime.now(UTC).isoformat(),
        )
        key = "csy_" + secrets.token_urlsafe(24)
        self._runs[run.id] = run
        self._keys[_digest(key)] = run.id
        return RunCreated(id=run.id, key=key)

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def by_key(self, key: str) -> Run | None:
        run_id = self._keys.get(_digest(key))
        return self._runs[run_id] if run_id else None

    def all(self) -> list[Run]:
        return list(self._runs.values())

    def add_step(
        self, run: Run, tool: str, args: dict[str, JsonValue], risk: Risk
    ) -> Step:
        step = Step(n=len(run.steps) + 1, tool=tool, args=args, risk=risk)
        run.steps.append(step)
        return step

    def holds(self) -> list[Hold]:
        return [
            Hold(run_id=r, task=self._runs[r].task, step=self._runs[r].steps[n - 1])
            for r, n in self._waiting
        ]

    async def hold(self, run: Run, step: Step, timeout: float) -> bool:
        """Wait for a human decision. The run's key stays revoked unless it's approved."""
        run.revoked = True
        step.status = "held"
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
        run.revoked = step.status != "approved"
        return not run.revoked

    def decide(self, run_id: str, n: int, approve: bool) -> bool:
        decision = self._waiting.get((run_id, n))
        if decision is None or decision.done():
            return False
        decision.set_result(approve)
        return True
