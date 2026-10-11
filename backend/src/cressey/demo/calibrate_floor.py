"""Calibrate the safety floor's two labels from the decision model (Jev) on labelled sets,
through the very questions Cressey asks (`ask_tool_kind`, `irreversibility`), so a new model
gets measured thresholds rather than guesses. The sets are ours (`data/eval/floor-labels.json`).
Only what Cressey would ask is measured: a tool the policy lists gets no label, and an action
that code already classes or holds isn't asked.

    uv run python -m cressey.demo.calibrate_floor   # live Jev, writes data/eval/floor-calibration.json
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, JsonValue

from cressey.core.floor import check
from cressey.core.judge import JevJudge, Judge, top
from cressey.core.models import Mandate, Policy, Run, Step, ToolRule
from cressey.core.proxy import ask_tool_kind, load_policy
from cressey.core.triangle import irreversibility
from cressey.guide.corpus import DATA
from cressey.settings import Settings

LABELS = DATA / "eval" / "floor-labels.json"
OUT = DATA / "eval" / "floor-calibration.json"
REPEATS = 2  # a threshold counts a case only if it holds for every answer
CANDIDATES = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.97, 0.99]


class ToolCase(BaseModel):
    tool: str
    kind: Literal["read", "write", "destructive"]


class ActionCase(BaseModel):
    irreversible: bool
    task: str
    mandate: Mandate = Mandate()
    tool: str
    args: dict[str, JsonValue]


class Labels(BaseModel):
    tools: list[ToolCase]
    actions: list[ActionCase]


class ToolRow(ToolCase):
    read: list[float | None]  # Jev's probability that the tool only reads, per answer
    top: list[str | None]


class ActionRow(ActionCase):
    p: list[
        float | None
    ]  # Jev's probability that the action can't be undone, per answer


class CodeDecides(BaseModel):
    tool: str
    args: dict[str, JsonValue]
    code: str  # code's reason, or the risk class it gives a call it doesn't hold


class ReadFloor(BaseModel):
    floor: float
    reads_kept: int
    reads: int
    others_as_read: int
    others: int


class Held(BaseModel):
    threshold: float
    held: int
    irreversible: int
    false_holds: int
    undoable: int


class Calibration(BaseModel):
    model: str
    date: str
    repeats: int
    listed_in_policy: list[str]
    code_decides: list[CodeDecides]
    tools: list[ToolRow]
    read_floor: list[ReadFloor]
    actions: list[ActionRow]
    irreversible: list[Held]


def action_step(case: ActionCase) -> tuple[Run, Step]:
    """The action as the proxy records it: a fresh run's first step, its arguments as JSON."""
    step = Step(
        n=1,
        tool=case.tool,
        args=json.dumps(case.args, ensure_ascii=False),
        risk="write",
    )
    run = Run(
        id="calibration",
        task=case.task,
        mandate=case.mandate,
        visibility="messages",
        kind="live",
        started_at=datetime.now(UTC).isoformat(),
        steps=[step],
    )
    return run, step


def code_decides(case: ActionCase, policy: Policy) -> str | None:
    """What code makes of an action it doesn't let through as a write; None when Jev is
    asked. A tool the policy doesn't list is taken as one Jev labelled a write."""
    rule = policy.tools.get(case.tool) or ToolRule(kind="write")
    risk, reason = check(rule, case.args, case.mandate)
    return reason or (None if risk == "write" else risk)


def _at_least(answers: list[float | None], x: float) -> list[bool]:
    return [p is not None and p >= x for p in answers]


def read_floor(rows: list[ToolRow], floor: float) -> ReadFloor:
    """Reads kept as reads, and other tools passed as reads, from this floor."""
    reads = [r for r in rows if r.kind == "read"]
    others = [r for r in rows if r.kind != "read"]
    return ReadFloor(
        floor=floor,
        reads_kept=sum(all(_at_least(r.read, floor)) for r in reads),
        reads=len(reads),
        others_as_read=sum(any(_at_least(r.read, floor)) for r in others),
        others=len(others),
    )


def held(rows: list[ActionRow], threshold: float) -> Held:
    """Irreversible actions held, and undoable ones held by mistake, from this threshold."""
    sure = [r for r in rows if r.irreversible]
    undoable = [r for r in rows if not r.irreversible]
    return Held(
        threshold=threshold,
        held=sum(all(_at_least(r.p, threshold)) for r in sure),
        irreversible=len(sure),
        false_holds=sum(any(_at_least(r.p, threshold)) for r in undoable),
        undoable=len(undoable),
    )


async def calibrate(
    judge: Judge, model: str, policy: Policy, labels: Labels
) -> Calibration:
    tools = [c for c in labels.tools if c.tool not in policy.tools]
    decided = {i: code_decides(c, policy) for i, c in enumerate(labels.actions)}
    asked = [c for i, c in enumerate(labels.actions) if decided[i] is None]

    async def kind(case: ToolCase) -> tuple[float | None, str | None]:
        answer = await ask_tool_kind(judge, case.tool)
        if not isinstance(answer, dict):
            return None, None
        return answer.get("read", 0.0), top(answer)

    async def irreversible(case: ActionCase) -> float | None:
        run, step = action_step(case)
        return await irreversibility(run, step, judge, policy.triangle)

    kinds = await asyncio.gather(*(kind(c) for c in tools for _ in range(REPEATS)))
    ps = await asyncio.gather(*(irreversible(c) for c in asked for _ in range(REPEATS)))
    tool_rows = [
        ToolRow(
            **c.model_dump(),
            read=[r for r, _ in kinds[i * REPEATS : (i + 1) * REPEATS]],
            top=[t for _, t in kinds[i * REPEATS : (i + 1) * REPEATS]],
        )
        for i, c in enumerate(tools)
    ]
    action_rows = [
        ActionRow(**c.model_dump(), p=ps[i * REPEATS : (i + 1) * REPEATS])
        for i, c in enumerate(asked)
    ]
    return Calibration(
        model=model,
        date=datetime.now(UTC).date().isoformat(),
        repeats=REPEATS,
        listed_in_policy=[c.tool for c in labels.tools if c.tool in policy.tools],
        code_decides=[
            CodeDecides(tool=c.tool, args=c.args, code=code)
            for i, c in enumerate(labels.actions)
            if (code := decided[i]) is not None
        ],
        tools=tool_rows,
        read_floor=[read_floor(tool_rows, x) for x in CANDIDATES],
        actions=action_rows,
        irreversible=[held(action_rows, x) for x in CANDIDATES],
    )


def summary(report: Calibration, policy: Policy) -> str:
    f = read_floor(report.tools, policy.floor.read)
    h = held(report.actions, policy.floor.irreversible)
    return (
        f"{report.model}, each case asked {report.repeats} times\n"
        f"tool kinds, a read from {f.floor}: {f.reads_kept}/{f.reads} reads kept, "
        f"{f.others_as_read}/{f.others} other tools passed as a read\n"
        f"irreversible from {h.threshold}: {h.held}/{h.irreversible} held, "
        f"{h.false_holds}/{h.undoable} undoable actions held by mistake "
        f"({len(report.code_decides)} actions left to code)"
    )


def main() -> None:
    judge = JevJudge.from_settings(Settings(model_mode="live"))
    if judge.ask is None:
        raise SystemExit("calibration needs the decision model: set TYPESAFE_API_KEY")
    policy = load_policy(DATA / "policy.yaml")
    labels = Labels.model_validate_json(LABELS.read_text())
    report = asyncio.run(calibrate(judge, judge.model, policy, labels))
    OUT.write_text(report.model_dump_json(indent=1) + "\n")
    print(summary(report, policy))


if __name__ == "__main__":
    main()
