from collections.abc import Mapping

import pytest

from cressey.core.proxy import load_policy
from cressey.demo.calibrate_floor import (
    LABELS,
    ActionCase,
    Labels,
    ToolCase,
    calibrate,
    summary,
)
from cressey.guide.corpus import DATA

pytestmark = pytest.mark.anyio
POLICY = load_policy(DATA / "policy.yaml")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class ScriptedJudge:
    """A tool reads when its name says get; an action is irreversible when it destroys."""

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "kind" in questions:
            read = 0.99 if "get" in state["tool"] else 0.2
            return {"kind": {"read": read, "write": 1 - read, "destructive": 0.0}}
        if "irreversible" in questions:
            args = state["current_step"]["args"]
            return {"irreversible": 0.9 if "destroy" in args else 0.1}
        return dict.fromkeys(questions, 0.0)


def bash(irreversible: bool, command: str) -> ActionCase:
    return ActionCase(
        irreversible=irreversible, task="t", tool="Bash", args={"command": command}
    )


def test_the_sets_are_labelled_and_balanced():
    labels = Labels.model_validate_json(LABELS.read_text())
    kinds = [c.kind for c in labels.tools]
    assert kinds.count("read") >= 50 and len(kinds) - kinds.count("read") >= 50
    sure = [c.irreversible for c in labels.actions]
    assert sum(sure) >= 20 and len(sure) - sum(sure) >= 20


async def test_only_what_cressey_would_ask_is_measured():
    labels = Labels(
        tools=[
            ToolCase(tool="mcp__x__get_thing", kind="read"),
            ToolCase(tool="mcp__x__set_thing", kind="write"),
            ToolCase(tool="Bash", kind="write"),  # listed in the policy: never asked
        ],
        actions=[
            bash(True, "terraform destroy -auto-approve"),
            bash(False, "npm install"),
            bash(True, "rm -rf build"),  # code holds it
            bash(False, "ls -la"),  # code reads it
        ],
    )
    report = await calibrate(ScriptedJudge(), "scripted", POLICY, labels)
    assert report.listed_in_policy == ["Bash"]
    assert [c.code for c in report.code_decides] == [
        "destructive shell command",
        "read",
    ]
    assert [r.tool for r in report.tools] == ["mcp__x__get_thing", "mcp__x__set_thing"]
    assert [r.p for r in report.actions] == [[0.9, 0.9], [0.1, 0.1]]
    assert summary(report, POLICY).splitlines()[1:] == [
        "tool kinds, a read from 0.95: 1/1 reads kept, 0/1 other tools passed as a read",
        (
            "irreversible from 0.5: 1/1 held, 0/1 undoable actions held by mistake "
            "(2 actions left to code)"
        ),
    ]
