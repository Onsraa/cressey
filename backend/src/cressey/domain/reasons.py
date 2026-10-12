"""Why Cressey held, alerted on or refused a call, as data: the check that fired, what it fired
on, and the model's score when a model's label fired. The text people read is built from it,
so a check is found by what it is, never by how its sentence is worded."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

Check = Literal[
    # The safety floor's code rules.
    "unknown_tool",
    "destructive_tool",
    "destructive_shell",
    "unclassified_sql",
    "destructive_sql",
    "egress",
    "protected_path",
    "frozen_path",
    # Tripwires, whatever the mandate.
    "trap_key",
    "self_call",
    # Jev's labels on the floor.
    "irreversible",
    "production",
    "no_answer",
    # The triangle, from the facts and the judgment, or closed in the agent's words.
    "triangle",
    "thought",
    "read_only",
]
FLOOR_RULES: frozenset[Check] = frozenset(
    {
        "unknown_tool",
        "destructive_tool",
        "destructive_shell",
        "unclassified_sql",
        "destructive_sql",
        "egress",
        "protected_path",
        "frozen_path",
    }
)
TEXT: dict[Check, str] = {
    "unknown_tool": "tool not in the policy",
    "destructive_tool": "irreversible action",
    "destructive_shell": "destructive shell command",
    "unclassified_sql": "SQL Cressey can't classify",
    "destructive_sql": "destructive SQL outside the mandate: {target}",
    "egress": "send outside the mandate: {target}",
    "protected_path": "protected path: {target}",
    "frozen_path": "frozen path: {target}",
    "trap_key": "trap key used: {target}",
    "self_call": "call to Cressey itself",
    "irreversible": "Jev: irreversible beyond the mandate, {score:.2f}",
    "production": "Jev: changes production, {score:.2f}",
    "no_answer": "Jev didn't answer",
    "triangle": "triangle: {target} confirmed",
    "thought": "triangle: closed in the agent's words, “{target}”",
    "read_only": "read-only key: pressure and opportunity confirmed",
}


class Reason(BaseModel):
    check: Check
    # What it fired on: tables, recipients, a path, a trap key's name, the legs, a thought.
    target: str | None = None
    score: float | None = None  # the model's probability, for Jev's labels
    afterwards: bool = False  # read after the call ran: it was too long to read first

    @property
    def text(self) -> str:
        said = TEXT[self.check].format(target=self.target, score=self.score or 0.0)
        return f"{said} (read afterwards)" if self.afterwards else said

    @property
    def key(self) -> tuple[Check, str | None]:
        """What the reason is about, whatever its score: two holds share it when they fired
        the same check on the same target."""
        return self.check, self.target


# What a held call went after: its tool, and each check with what it fired on.
Target = tuple[str, tuple[tuple[Check, str | None], ...]]


def target(tool: str, reasons: Sequence[Reason]) -> Target:
    return tool, tuple(r.key for r in reasons)


def joined(reasons: Sequence[Reason]) -> str | None:
    """The reasons as one line, as the dashboard shows them; None for no reason."""
    return "; ".join(r.text for r in reasons) or None
