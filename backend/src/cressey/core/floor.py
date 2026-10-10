"""Safety floor: code classifies each call and holds irreversible actions, or data
leaving, outside the task's mandate. Anything it can't classify counts as destructive."""

import re
from collections.abc import Mapping

import sqlglot
from pydantic import JsonValue
from sqlglot import exp

from cressey.core.models import Mandate, Risk, ToolRule

RANK: tuple[Risk, ...] = ("read", "write", "destructive")
# sqlglot can't parse REPLACE INTO (S4). It inserts or overwrites rows: classed as a write.
REPLACE_INTO = re.compile(r"(^|;)(\s*)REPLACE\s+INTO\b", re.IGNORECASE)


def _statement_risk(s: exp.Expr) -> Risk | None:
    """None when code can't classify the statement."""
    if s.find(exp.Delete, exp.Drop, exp.TruncateTable) or any(
        not u.args.get("where") for u in s.find_all(exp.Update)
    ):
        return "destructive"
    if s.find(exp.Insert, exp.Update, exp.Merge, exp.Create, exp.Alter):
        return "write"
    if isinstance(s, (exp.Query, exp.Transaction, exp.Commit, exp.Rollback)):
        return "read"
    return None


def sql_risk(sql: str) -> tuple[Risk, set[str] | None]:
    """Risk of a SQL string, and the tables its destructive statements touch
    (None when a statement can't be classified)."""
    try:
        parsed = sqlglot.parse(REPLACE_INTO.sub(r"\1\2INSERT INTO", sql))
        statements = [s for s in parsed if s is not None]
    except sqlglot.errors.SqlglotError:
        return "destructive", None
    if not statements:
        return "destructive", None
    risk: Risk = "read"
    tables: set[str] = set()
    for s in statements:
        r = _statement_risk(s)
        if r is None:
            return "destructive", None
        if r == "destructive":
            tables |= {t.name for t in s.find_all(exp.Table)}
        risk = max(risk, r, key=RANK.index)
    return risk, tables


def _may_send(address: str, mandate: Mandate) -> bool:
    a = address.strip().lower()
    return any(
        a == m.lower() or (m.startswith("@") and a.endswith(m.lower()))
        for m in mandate.may_send_to
    )


def check(
    rule: ToolRule | None, args: Mapping[str, JsonValue], mandate: Mandate
) -> tuple[Risk, str | None]:
    """The call's risk class and, when the safety floor holds it, why."""
    if rule is None:
        return "destructive", "outil absent de la politique"
    value = args.get(rule.arg) if rule.arg else None
    match rule.kind:
        case "read" | "write":
            return rule.kind, None
        case "destructive":
            return "destructive", "action irréversible"
        case "sql":
            risk, tables = sql_risk(value if isinstance(value, str) else "")
            if risk != "destructive":
                return risk, None
            if not tables:
                return risk, "SQL que Cressey ne sait pas classer"
            outside = sorted(tables - set(mandate.may_destroy))
            return risk, (
                f"SQL destructeur hors mandat : {', '.join(outside)}"
                if outside
                else None
            )
        case "egress":
            recipients = value if isinstance(value, list) else [value]
            outside = [
                str(r)
                for r in recipients
                if not (isinstance(r, str) and _may_send(r, mandate))
            ]
            # Data that left can't be recalled: weighted like a destructive action.
            return "destructive", (
                f"envoi hors mandat : {', '.join(outside)}" if outside else None
            )
