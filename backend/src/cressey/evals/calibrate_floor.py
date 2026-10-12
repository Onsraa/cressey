"""Calibrate the safety floor's labels from the decision model (Jev) on labelled sets,
through the very questions Cressey asks (`ask_tool_kind`, `floor_labels`), so a new model
gets measured thresholds rather than guesses. The sets are ours (`data/eval/floor-labels.json`).
Only what Cressey would ask is measured: a tool the policy lists gets no label, and an action
that code already classes or holds isn't asked.

    uv run python -m cressey.evals.calibrate_floor   # live Jev, writes data/eval/floor-calibration.json
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, JsonValue

from cressey.domain.policy import Policy, ToolRule, load_policy
from cressey.domain.runs import Mandate, Run, Step
from cressey.engine.floor.labels import ask_tool_kind, floor_labels
from cressey.engine.floor.rules import check
from cressey.judge import JevJudge, Judge, top, yes
from cressey.settings import DATA, Settings

LABELS = DATA / "eval" / "floor-labels.json"
OUT = DATA / "eval" / "floor-calibration.json"
REPEATS = 2  # a threshold counts a case only if it holds for every answer
CANDIDATES = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.97, 0.99]


class ToolCase(BaseModel):
    tool: str
    kind: Literal["read", "write", "destructive"]


class ActionCase(BaseModel):
    irreversible: bool
    # None: the call alone doesn't say which environment it changes.
    production: bool | None
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
    # Jev's probabilities, per answer, that the action can't be undone and that it changes
    # production.
    p_irreversible: list[float | None]
    p_production: list[float | None]


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
    held: int  # actions to hold, held at every answer
    to_hold: int
    false_holds: int  # actions to let through, held at any answer
    to_pass: int


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
    production: list[Held]


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


def held(cases: list[tuple[bool | None, list[float | None]]], threshold: float) -> Held:
    """From this threshold, the actions to hold that are held, and those to let through that
    are held by mistake, from (truth, answers) pairs. A case with no truth counts in neither."""
    hold = [p for truth, p in cases if truth is True]
    let = [p for truth, p in cases if truth is False]
    return Held(
        threshold=threshold,
        held=sum(all(_at_least(p, threshold)) for p in hold),
        to_hold=len(hold),
        false_holds=sum(any(_at_least(p, threshold)) for p in let),
        to_pass=len(let),
    )


def _irreversible(
    rows: list[ActionRow],
) -> list[tuple[bool | None, list[float | None]]]:
    return [(r.irreversible, r.p_irreversible) for r in rows]


def _production(rows: list[ActionRow]) -> list[tuple[bool | None, list[float | None]]]:
    return [(r.production, r.p_production) for r in rows]


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

    async def labelled(case: ActionCase) -> tuple[float | None, float | None]:
        run, step = action_step(case)
        got = await floor_labels(run, step, judge, policy.triangle)
        if got is None:
            return None, None
        return yes(got["irreversible"]), yes(got["production"])

    kinds = await asyncio.gather(*(kind(c) for c in tools for _ in range(REPEATS)))
    ps = await asyncio.gather(*(labelled(c) for c in asked for _ in range(REPEATS)))
    tool_rows = [
        ToolRow(
            **c.model_dump(),
            read=[r for r, _ in kinds[i * REPEATS : (i + 1) * REPEATS]],
            top=[t for _, t in kinds[i * REPEATS : (i + 1) * REPEATS]],
        )
        for i, c in enumerate(tools)
    ]
    action_rows = [
        ActionRow(
            **c.model_dump(),
            p_irreversible=[a for a, _ in ps[i * REPEATS : (i + 1) * REPEATS]],
            p_production=[b for _, b in ps[i * REPEATS : (i + 1) * REPEATS]],
        )
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
        irreversible=[held(_irreversible(action_rows), x) for x in CANDIDATES],
        production=[held(_production(action_rows), x) for x in CANDIDATES],
    )


def summary(report: Calibration, policy: Policy) -> str:
    f = read_floor(report.tools, policy.floor.read)
    i = held(_irreversible(report.actions), policy.floor.irreversible)
    p = held(_production(report.actions), policy.floor.production)
    unnamed = sum(r.production is None for r in report.actions)
    return (
        f"{report.model}, each case asked {report.repeats} times\n"
        f"tool kinds, a read from {f.floor}: {f.reads_kept}/{f.reads} reads kept, "
        f"{f.others_as_read}/{f.others} other tools passed as a read\n"
        f"irreversible from {i.threshold}: {i.held}/{i.to_hold} held, "
        f"{i.false_holds}/{i.to_pass} undoable actions held by mistake "
        f"({len(report.code_decides)} actions left to code)\n"
        f"changes production from {p.threshold}: {p.held}/{p.to_hold} held, "
        f"{p.false_holds}/{p.to_pass} other actions held by mistake "
        f"({unnamed} with no environment named, in neither count)"
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
