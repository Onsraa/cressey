"""Safety floor: code classifies each call and holds irreversible actions, or data
leaving, outside the task's mandate. Anything it can't classify counts as destructive.
A call that carries a trap key is caught whatever the mandate: the proxy holds it when
it changes something and flags it when it only reads."""

import fnmatch
import json
import posixpath
import re
from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

import sqlglot
from pydantic import JsonValue
from sqlglot import exp

from cressey.core.trace import decoded, strings
from cressey.domain.policy import ToolRule
from cressey.domain.runs import Mandate, Risk

RANK: tuple[Risk, ...] = ("read", "write", "destructive")
# Shell commands (the Claude Code hook). A command made only of these, with no redirection
# to a file, reads; one that deletes files, rows or tables, or rewrites history, is
# destructive; any other is a write the triangle judges. A curl or wget that only reads is
# a read too.
READ_COMMANDS = {
    "cat", "cd", "diff", "echo", "env", "file", "find", "grep", "head", "jq", "ls",
    "printenv", "pwd", "rg", "sleep", "sort", "stat", "tail", "tree", "uniq", "wc", "which",
    "git status", "git diff", "git log", "git show", "git branch", "sed -n",
}  # fmt: skip
DESTRUCTIVE_COMMAND = re.compile(
    r"\brm\s|\bdrop\s+(?:table|database|schema|index)\b|\btruncate\b|\bdelete\s+from\b"
    r"|\bgit\s+push\b[^|;&]*(?:--force\b|\s-f\b)|\bgit\s+(?:reset\s+--hard|clean\s)",
    re.IGNORECASE,
)
# $(...), `...`, <(...), >(...) and zsh's =(...) run a command wherever they sit, whatever
# the first word.
SUBSTITUTION = re.compile(r"\$\(|`|[<>=]\(")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
# find's actions that run or delete something.
FIND_ACTIONS = {"-exec", "-execdir", "-ok", "-okdir", "-delete"}
MUTATION = re.compile(r"\bmutation\b", re.IGNORECASE)
GRAPHQL_DOCUMENT = re.compile(r"\{|(?:query|fragment)\b")
# A body whose text isn't what the server sees: expanded by the shell, or JSON-escaped
# (\u006dutation). MUTATION is looked for in the decoded query, where \nmutation has a
# word boundary that the raw JSON hides.
INDIRECT = re.compile(r"\$|\\u")
# Options that send a body or a file, or take the request from elsewhere (-K reads a config
# file, --expand-* expands variables, --next starts a second transfer, -Q runs commands over
# FTP) or write a local file (--remote-name; -o and -O are read below).
WRITE_FLAGS = {
    "-F", "--form", "--form-string", "-T", "--upload-file", "--post-file", "--post-data",
    "-K", "--config", "-Q", "--quote", "--next", "--remote-name", "--remote-name-all",
}  # fmt: skip
WGET_WRITE_FLAGS = {"-e", "--execute"}  # a startup command can set the method or body
METHOD_FLAGS = {"-X", "--request", "--method"}
# curl's short options that take a value; in a cluster (-sXPOST, -sd) the first one ends it.
VALUE_OPTIONS = set("AbcCdDeEFHKmoPQrtTuUwxXyYz")
WGET_VALUE_OPTIONS = set("eoaiBtOTwQPUlARDIX")
# curl's short options that write a file (-O) or start a second transfer (-:), with no value.
BARE_WRITES = set("O:")
# A redirection that writes nothing: to /dev/null, or duplicating a file descriptor (2>&1).
HARMLESS_REDIRECT = re.compile(
    r"(?:&|\d*)>>?\s*/dev/null(?![^\s;&|()])|\d*>&\d+(?![^\s;&|()])"
)
# A host and port a call names: in a URL (its port, else its scheme's), or bare, host:port.
ORIGIN = re.compile(
    r"(?P<scheme>https?|wss?)://(?P<host>\[[0-9A-Fa-f:.]+\]|[\w.-]+)(?::(?P<port>\d{1,5}))?"
    r"|(?P<bare>\[[0-9A-Fa-f:.]+\]|[\w.-]+):(?P<bare_port>\d{1,5})\b"
)
DEFAULT_PORTS = {"http": 80, "ws": 80, "https": 443, "wss": 443}
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


def _command(words: list[str]) -> list[str]:
    """The words from the command itself: `export` and NAME=value prefixes dropped."""
    skip = 0
    while skip < len(words) and (
        words[skip] == "export" or ASSIGNMENT.match(words[skip])
    ):
        skip += 1
    return words[skip:]


def _http_risk(words: list[str]) -> Risk:
    """Risk of a curl or wget call: a read unless it uploads, writes a file (a wget reads only
    into stdout, -O -), or sends a body or method that isn't a GraphQL query's (those travel
    as POST, so POST alone is not enough to write)."""
    wget = words[0] == "wget"
    value_options = WGET_VALUE_OPTIONS if wget else VALUE_OPTIONS
    output = ("-O", "--output-document") if wget else ("-o", "--output")
    bodies: list[str] = []
    post = to_stdout = False
    rest = iter(words[1:])
    for word in rest:
        if word.startswith("--"):
            flag, _, value = word.partition("=")
            if flag.startswith("--expand-"):
                return "write"
        elif word.startswith("-"):
            i = next(
                (i for i, c in enumerate(word) if i and c in value_options), len(word)
            )
            if not wget and BARE_WRITES & set(word[1:i]):
                return "write"
            if i == len(word):
                continue
            flag, value = "-" + word[i], word[i + 1 :]
        else:
            continue
        if flag in WRITE_FLAGS or (wget and flag in WGET_WRITE_FLAGS):
            return "write"
        if flag in output:
            if (value or next(rest, "")) not in ("-", "/dev/null"):
                return "write"
            to_stdout = True
        elif flag in METHOD_FLAGS:
            method = (value or next(rest, "")).upper()
            if method not in ("GET", "HEAD", "POST"):
                return "write"
            post = post or method == "POST"
        elif flag in ("-d", "--json") or flag.startswith("--data"):
            bodies.append(value or next(rest, ""))
    if (wget and not to_stdout) or (post and not bodies):
        return "write"
    return "read" if all(map(_is_query, bodies)) else "write"


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """json.loads's object hook for a body: a key given twice is read as the server likes."""
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate key")
    return dict(pairs)


def _is_document(text: str) -> bool:
    """Whether a string opens like a GraphQL query document: after blank and `#` comment
    lines, a `{`, `query` or `fragment`. SQL sent over HTTP ({"query": "UPDATE ..."}) doesn't."""
    lines = (line.strip() for line in text.splitlines())
    first = next((line for line in lines if line and not line.startswith("#")), "")
    return bool(GRAPHQL_DOCUMENT.match(first))


def _is_query(body: str) -> bool:
    """An inline GraphQL query, not a mutation: a JSON object whose top-level "query" is a
    query document (an Elasticsearch {"query": {...}} is not)."""
    try:
        parsed = json.loads(body, object_pairs_hook=_unique)
    except ValueError:
        return False
    return (
        isinstance(parsed, dict)
        and isinstance(parsed.get("query"), str)
        and _is_document(parsed["query"])
        and not INDIRECT.search(body)
        and not MUTATION.search(parsed["query"])
    )


def _reads(words: list[str]) -> bool:
    """Whether a command other than curl or wget only reads (see READ_COMMANDS)."""
    if not {words[0], " ".join(words[:2])} & READ_COMMANDS:
        return False
    if words[0] == "env":  # env running a command
        return not _command(words[1:])
    if words[0] == "find":
        return not FIND_ACTIONS & set(words)
    return True


def _simple_commands(command: str) -> list[list[str]] | None:
    """The words of each simple command of a shell command line, read as POSIX shells do:
    blanks are space and tab; newline ; & | ( ) end a command; backslash, '...', "..." and
    $'...' quote; backslash-newline joins; a # starts a comment only at the start of a word.
    None when the line can't be told: a here-document, an open quote, a trailing backslash,
    an escape in $'...'. (shlex won't do: it reads a#b, and a # after an escaped blank,
    as comments.)"""
    commands: list[list[str]] = [[]]
    word: str | None = None  # the word being read; '' is a word too
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        # >& and &> are redirections, not a separator (bash and zsh read &> that way).
        if command.startswith(("&>", ">&"), i):
            word = (word or "") + command[i : i + 2]
            i += 2
        elif c in " \t\n;&|()":
            if word is not None:
                commands[-1].append(word)
                word = None
            if c not in " \t":
                commands.append([])
            i += 1
        elif c == "#" and word is None:
            end = command.find("\n", i)
            i = n if end < 0 else end
        elif command.startswith("<<", i):
            return None
        elif c == "\\":
            if i + 1 == n:
                return None
            if command[i + 1] != "\n":
                word = (word or "") + command[i + 1]
            i += 2
        elif c == "'" or command.startswith("$'", i):
            ansi = c == "$"
            start = i + (2 if ansi else 1)
            end = command.find("'", start)
            if end < 0 or (ansi and "\\" in command[start:end]):
                return None
            word = (word or "") + command[start:end]
            i = end + 1
        elif c == '"':
            word = word or ""
            i += 1
            while i < n and command[i] != '"':
                ch = command[i]
                if ch == "\\" and i + 1 < n and command[i + 1] in '"\\$`\n':
                    i += 1
                    ch = "" if command[i] == "\n" else command[i]
                word += ch
                i += 1
            if i == n:
                return None
            i += 1
        else:
            word = (word or "") + c
            i += 1
    if word is not None:
        commands[-1].append(word)
    return [words for words in commands if words]


def shell_risk(command: str) -> Risk:
    """Risk of a shell command, from the commands it runs (see READ_COMMANDS)."""
    if DESTRUCTIVE_COMMAND.search(command):
        return "destructive"
    simple = _simple_commands(command)
    redirects = HARMLESS_REDIRECT.sub(" ", command)
    if simple is None or ">" in redirects or SUBSTITUTION.search(command):
        return "write"
    for words in map(_command, simple):
        if not words:
            continue
        if words[0] in ("curl", "wget"):
            risk = _http_risk(words)
            if risk != "read":
                return risk
        elif not _reads(words):
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


def _host(host: str) -> str:
    """One name for this machine, however it is spelled: localhost, 127.0.0.0/8, ::1, and
    the any-address, which connects here too."""
    h = host.strip("[]").lower()
    if h in ("localhost", "::1", "0.0.0.0", "::") or h.startswith("127."):
        return "localhost"
    return h


def origin(url: str) -> tuple[str, int]:
    """The host and port a URL reaches."""
    u = urlsplit(url)
    return _host(u.hostname or ""), u.port or DEFAULT_PORTS.get(u.scheme, 80)


def edits_a_file(rule: ToolRule | None) -> bool:
    """A write to a file at a path this floor checks against the mandate (protected, frozen):
    what it does is known before it runs, and it contacts nothing."""
    return rule is not None and rule.kind == "write" and rule.arg is not None


def at_cressey(
    rule: ToolRule | None,
    args: Mapping[str, JsonValue],
    guarded: Iterable[tuple[str, int]],
) -> str | None:
    """Why the safety floor holds a call that would reach Cressey itself, its API or its
    dashboard, whatever the mandate: an agent has no business with its guard. What a file
    edit writes contacts nothing, so it isn't read. A tripwire, not the lock: the admin key
    is that (a host spelled another way, or a URL built at run time, goes unseen)."""
    if edits_a_file(rule):
        return None
    targets = set(guarded)
    text = " ".join(s for value in args.values() for s in strings(value))
    for m in ORIGIN.finditer(text):
        host, port = m["host"] or m["bare"], m["port"] or m["bare_port"]
        reached = _host(host), int(port) if port else DEFAULT_PORTS[m["scheme"]]
        if reached in targets:
            return "call to Cressey itself"
    return None
