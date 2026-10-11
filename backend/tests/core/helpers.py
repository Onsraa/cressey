from cressey.core.models import Mandate, Message, Run, Step

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
