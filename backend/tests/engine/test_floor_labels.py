"""Jev's labels on the safety floor: what it reads of a call."""

import json
from collections.abc import Mapping

import pytest

from cressey.domain.policy import Thresholds
from cressey.engine.floor.labels import floor_labels
from cressey.scan.secrets import fingerprint, redact
from cressey.testing import no_to_all
from tests.helpers import run_with, step

pytestmark = pytest.mark.anyio
TRAP = "rlw_trap_0123456789abcdef"  # a trap key: no scanner rule finds it on its own


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Reads:
    """Answers no to everything, and keeps what it was shown."""

    def __init__(self) -> None:
        self.shown: list[str] = []

    async def answers(self, state: dict, questions: Mapping) -> dict:
        self.shown.append(state["current_step"]["args"])
        return no_to_all(questions)


async def test_neither_reading_shows_a_value_the_caller_hides():
    """The reading without the agent's words hides what the shown arguments hide, the trap
    keys included: Jev never reads a trap key's value."""
    hidden = {TRAP: fingerprint(TRAP)}
    raw = {"command": f"deploy --token {TRAP}", "description": "Routine deploy"}
    call = step(
        1,
        "Bash",
        args=redact(json.dumps(raw, ensure_ascii=False), hidden),
        risk="write",
        raw_args=raw,
    )
    judge = Reads()
    await floor_labels(run_with(), call, judge, Thresholds(), ["description"], hidden)
    assert len(judge.shown) == 2  # with the words, then without
    assert all(TRAP not in shown for shown in judge.shown)
