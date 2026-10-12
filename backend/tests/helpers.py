import asyncio
from collections.abc import Mapping

from pydantic import JsonValue
from typesafe_sdk import Noul

from cressey.domain.acts import Act, Agent
from cressey.domain.runs import Mandate, Message, Run, Step

TASK = "fais passer les tests avant la mise en prod de ce soir"


def step(n, tool="run_tests", args="{}", risk="read", **kw) -> Step:
    return Step(n=n, tool=tool, args=args, risk=risk, **kw)


def run_with(
    *steps: Step, mandate: Mandate | None = None, task: str = TASK, **kw
) -> Run:
    return Run(
        id="r1",
        task=task,
        mandate=mandate or Mandate(),
        visibility="messages",
        kind="live",
        started_at="2026-10-10T12:00:00+00:00",
        steps=list(steps),
        **kw,
    )


def message(
    after=0,
    text="",
    thoughts=None,
    source="narration",
    streaming=False,
    role="agent",
) -> Message:
    return Message(
        after=after,
        text=text,
        role=role,
        streaming=streaming,
        source=source,
        thoughts=thoughts or [],
    )


class ServedJudge:
    """The decision model of a served app. The triangle's questions get zeros. A thought
    gets its row in `thoughts` (question -> answer, as ScriptedJudge reads them; None for no
    answer), after `delay` seconds. `asked` holds the states of the case's questions,
    recorded before the wait."""

    def __init__(self) -> None:
        self.thoughts: dict[str, dict | None] = {}
        self.delay = 0.0
        self.asked: list[dict] = []

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "current_thought" not in state:
            return dict.fromkeys(questions, 0.0)
        self.asked.append(state)
        await asyncio.sleep(self.delay)
        row = self.thoughts.get(state["current_thought"], {})
        if row is None:  # a thought scripted as unanswered
            return None
        return {
            name: row.get(
                name, 0.0 if isinstance(q, Noul) else dict.fromkeys(q.criteria, 0.0)
            )
            for name, q in questions.items()
        }


def act(tool: str, args: dict[str, JsonValue] | None = None) -> Act:
    """A call through the MCP gateway, by a client that named nothing."""
    return Act(surface="mcp", agent=Agent(), tool=tool, args=args or {})
