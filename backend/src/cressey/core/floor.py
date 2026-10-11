"""Safety floor: code classifies each call and holds irreversible actions, or data
leaving, outside the task's mandate. Anything it can't classify counts as destructive.
A call that carries a trap key is held whatever the mandate."""

import fnmatch
import posixpath
import re
from collections.abc import Mapping

import sqlglot
from pydantic import JsonValue
from sqlglot import exp

from cressey.core.models import Mandate, Risk, ToolRule
from cressey.core.trace import decoded, strings

RANK: tuple[Risk, ...] = ("read", "write", "destructive")
# Shell commands (the Claude Code hook). A command made only of these, with no redirection,
# reads; one that deletes files, rows or tables, or rewrites history, is destructive; any
# other is a write the triangle judges.
READ_COMMANDS = {
    "cat", "cd", "diff", "echo", "env", "file", "find", "grep", "head", "jq", "ls",
    "printenv", "pwd", "rg", "sort", "stat", "tail", "tree", "uniq", "wc", "which",
    "git status", "git diff", "git log", "git show", "git branch", "sed -n",
}  # fmt: skip
DESTRUCTIVE_COMMAND = re.compile(
    r"\brm\s|\bdrop\s+(?:table|database|schema|index)\b|\btruncate\b|\bdelete\s+from\b"
    r"|\bgit\s+push\b[^|;&]*(?:--force\b|\s-f\b)|\bgit\s+(?:reset\s+--hard|clean\s)",
    re.IGNORECASE,
)
SEGMENT = re.compile(r"\|\|?|&&|;|\n")
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


def shell_risk(command: str) -> Risk:
    """Risk of a shell command, from the commands it runs (see READ_COMMANDS)."""
    if DESTRUCTIVE_COMMAND.search(command):
        return "destructive"
    if ">" in command:
        return "write"
    for segment in SEGMENT.split(command):
        words = segment.split()
        if words and not {words[0], " ".join(words[:2])} & READ_COMMANDS:
            return "write"
    return "read"


def _may_send(address: str, mandate: Mandate) -> bool:
    a = address.strip().lower()
    return any(
        a == m.lower() or (m.startswith("@") and a.endswith(m.lower()))
        for m in mandate.may_send_to
    )


def _under(path: str, globs: list[str]) -> bool:
    """A name covers everything under it; globs work too."""
    return any(
        path == g or path.startswith(g + "/") or fnmatch.fnmatchcase(path, g)
        for g in (g.strip("/").lower() for g in globs)
    )


def _guarded(path: JsonValue, mandate: Mandate, writing: bool) -> str | None:
    """Why the floor holds a read or write of a path the mandate guards, with no model asked.
    `protected` paths can be neither read nor written (the Hugging Face / METR read floor);
    `frozen` ones read but never write (ImpossibleBench: the cheating edited the tests).
    Case and `..` can't step around it."""
    if not isinstance(path, str):
        return None
    p = posixpath.normpath(path.replace("\\", "/")).lstrip("/").lower()
    if _under(p, mandate.protected):
        return f"protected path: {path}"
    if writing and _under(p, mandate.frozen):
        return f"frozen path: {path}"
    return None


def check(
    rule: ToolRule | None, args: Mapping[str, JsonValue], mandate: Mandate
) -> tuple[Risk, str | None]:
    """The call's risk class and, when the safety floor holds it, why."""
    if rule is None:
        return "destructive", "tool not in the policy"
    value = args.get(rule.arg) if rule.arg else None
    match rule.kind:
        case "read" | "write":
            return rule.kind, _guarded(value, mandate, rule.kind == "write")
        case "destructive":
            return "destructive", "irreversible action"
        case "shell":
            # shortcut: protected and frozen paths aren't matched inside a command, add it
            # when a mandate guards paths from a shell agent
            risk = shell_risk(value if isinstance(value, str) else "")
            return risk, "destructive shell command" if risk == "destructive" else None
        case "sql":
            risk, tables = sql_risk(value if isinstance(value, str) else "")
            if risk != "destructive":
                return risk, None
            if not tables:
                return risk, "SQL Cressey can't classify"
            outside = sorted(tables - set(mandate.may_destroy))
            return risk, (
                f"destructive SQL outside the mandate: {', '.join(outside)}"
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
                f"send outside the mandate: {', '.join(outside)}" if outside else None
            )


def trap(args: Mapping[str, JsonValue], decoys: Mapping[str, str]) -> str | None:
    """Why the safety floor holds a call that carries a trap key, whatever the mandate: in any
    argument, in any case, or in a token that decodes from base64, hex or URL encoding."""
    text = " ".join(s for value in args.values() for s in strings(value))
    forms = [form.lower() for form in (text, *decoded(text))]
    used = [
        name for name, key in decoys.items() if any(key.lower() in f for f in forms)
    ]
    return f"trap key used: {', '.join(used)}" if used else None
