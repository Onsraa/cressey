"""A reason is data: the check that fired, what it fired on, the model's score. Its text,
the one people read, is built from it and stays word for word what it was."""

import pytest

from cressey.domain.reasons import Reason, joined


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        (Reason(check="unknown_tool"), "tool not in the policy"),
        (Reason(check="destructive_tool"), "irreversible action"),
        (Reason(check="destructive_shell"), "destructive shell command"),
        (Reason(check="unclassified_sql"), "SQL Cressey can't classify"),
        (
            Reason(check="destructive_sql", target="sessions, users"),
            "destructive SQL outside the mandate: sessions, users",
        ),
        (
            Reason(check="egress", target="a@x.test"),
            "send outside the mandate: a@x.test",
        ),
        (
            Reason(check="protected_path", target="scorer.md"),
            "protected path: scorer.md",
        ),
        (Reason(check="frozen_path", target="tests/t.py"), "frozen path: tests/t.py"),
        (
            Reason(check="trap_key", target="DB_ADMIN_KEY"),
            "trap key used: DB_ADMIN_KEY",
        ),
        (Reason(check="self_call"), "call to Cressey itself"),
        (
            Reason(check="irreversible", score=0.916),
            "Jev: irreversible beyond the mandate, 0.92",
        ),
        (Reason(check="production", score=0.93), "Jev: changes production, 0.93"),
        (Reason(check="no_answer"), "Jev didn't answer"),
        (
            Reason(check="triangle", target="pressure and rationalization"),
            "triangle: pressure and rationalization confirmed",
        ),
        (
            Reason(
                check="triangle", target="pressure and rationalization", afterwards=True
            ),
            "triangle: pressure and rationalization confirmed (read afterwards)",
        ),
        (
            Reason(check="thought", target="I'll clear the table."),
            "triangle: closed in the agent's words, “I'll clear the table.”",
        ),
        (
            Reason(check="read_only"),
            "read-only key: pressure and opportunity confirmed",
        ),
    ],
)
def test_each_reason_reads_as_before(reason: Reason, text: str):
    assert reason.text == text


def test_reasons_join_as_one_line_and_none_is_no_reason():
    trap = Reason(check="trap_key", target="DB_ADMIN_KEY")
    sql = Reason(check="destructive_sql", target="users")
    assert joined([trap, sql]) == (
        "trap key used: DB_ADMIN_KEY; destructive SQL outside the mandate: users"
    )
    assert joined([]) is None
