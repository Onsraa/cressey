"""The safety floor's rules: code classifies each call by its tool's kind and holds
irreversible actions, or data leaving, outside the task's mandate. Anything it can't
classify counts as destructive."""

import fnmatch
import posixpath
from collections.abc import Mapping

from pydantic import JsonValue

from cressey.domain.policy import ToolRule
from cressey.domain.runs import Mandate, Risk
from cressey.engine.floor.shell import shell_risk
from cressey.engine.floor.sql import sql_risk


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


def edits_a_file(rule: ToolRule | None) -> bool:
    """A write to a file at a path this floor checks against the mandate (protected, frozen):
    what it does is known before it runs, and it contacts nothing."""
    return rule is not None and rule.kind == "write" and rule.arg is not None
