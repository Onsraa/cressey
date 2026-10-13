"""What a SQL string does, as code reads it, and the tables its destructive statements touch."""

import re

import sqlglot
from sqlglot import exp

from cressey.domain.runs import Risk

RANK: tuple[Risk, ...] = ("read", "write", "destructive")
# sqlglot can't parse REPLACE INTO (S4); INSERT OR REPLACE says the same and it parses.
REPLACE_INTO = re.compile(r"(^|;)(\s*)REPLACE\s+INTO\b", re.IGNORECASE)


def _overwrites(s: exp.Expr) -> bool:
    """Rows changed in place, whose old values are lost: any UPDATE whatever its WHERE (a
    WHERE 1 = 1 matches them all), a MERGE, or an insert that replaces or updates on conflict."""
    if s.find(exp.Update, exp.Merge):
        return True
    return any(
        str(i.args.get("alternative") or "").upper() == "REPLACE"
        or bool(c and c.args.get("expressions"))
        for i in s.find_all(exp.Insert)
        for c in [i.args.get("conflict")]
    )


def _statement_risk(s: exp.Expr) -> Risk | None:
    """None when code can't classify the statement."""
    if s.find(
        exp.Delete, exp.Drop, exp.TruncateTable, exp.AlterRename, exp.RenameColumn
    ) or _overwrites(s):
        return "destructive"
    if s.find(exp.Insert, exp.Create, exp.Alter):
        return "write"
    if isinstance(s, (exp.Query, exp.Transaction, exp.Commit, exp.Rollback)):
        return "read"
    return None


def sql_risk(sql: str) -> tuple[Risk, set[str] | None]:
    """Risk of a SQL string, and the tables its destructive statements touch
    (None when a statement can't be classified)."""
    try:
        parsed = sqlglot.parse(REPLACE_INTO.sub(r"\1\2INSERT OR REPLACE INTO", sql))
        statements = [s for s in parsed if s is not None]
    # sqlglot raises more than its own errors: a ValueError on `a->1e9`, a RecursionError when
    # nested deep
    except (sqlglot.errors.SqlglotError, ValueError, RecursionError):
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
