"""What a shell command does, as code reads it (the Claude Code hook)."""

import re

from cressey.domain.runs import Risk
from cressey.engine.floor.http import http_risk

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
# A redirection that writes nothing: to /dev/null, or duplicating a file descriptor (2>&1).
HARMLESS_REDIRECT = re.compile(
    r"(?:&|\d*)>>?\s*/dev/null(?![^\s;&|()])|\d*>&\d+(?![^\s;&|()])"
)
# SQL clients and the (short, long) flags that carry the SQL they run; sqlite3 and duckdb
# take it as an argument after the database file.
# shortcut: the client is the command's first word, so one behind a wrapper (sudo, docker
# exec, ssh) or a path isn't seen, nor a short flag glued to others (-tAc) or to its value
# (-cSQL), nor SQL piped or redirected into the client (`echo ... | psql`, `psql < q.sql`)
# or read from a file (`psql -f`): those keep the verdict shell_risk alone gives. Add the
# form when an agent's call needs it.
SQL_FLAGS = {
    "psql": ("-c", "--command"),
    "mysql": ("-e", "--execute"),
    "mariadb": ("-e", "--execute"),
    "clickhouse-client": ("-q", "--query"),
}
SQL_ARGUMENT = {"sqlite3", "duckdb"}


def _command(words: list[str]) -> list[str]:
    """The words from the command itself: `export` and NAME=value prefixes dropped."""
    skip = 0
    while skip < len(words) and (
        words[skip] == "export" or ASSIGNMENT.match(words[skip])
    ):
        skip += 1
    return words[skip:]


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
            risk = http_risk(words)
            if risk != "read":
                return risk
        elif not _reads(words):
            return "write"
    return "read"


def inline_sql(command: str) -> list[str]:
    """The SQL each simple command of a shell command line passes inline to a SQL client:
    the value of its flag (see SQL_FLAGS), given as `-c SQL`, `--command SQL` or
    `--command=SQL`, or the arguments of sqlite3 and duckdb after the database file. []
    when the line can't be told (see _simple_commands)."""
    sql: list[str] = []
    for words in map(_command, _simple_commands(command) or []):
        if not words:
            continue
        client, args = words[0], words[1:]
        if client in SQL_FLAGS:
            short, long = SQL_FLAGS[client]
            for i, arg in enumerate(args):
                if arg.startswith(long + "="):
                    sql.append(arg.removeprefix(long + "="))
                elif arg in (short, long) and i + 1 < len(args):
                    sql.append(args[i + 1])
        elif client in SQL_ARGUMENT:
            # The first word that isn't an option is the database file.
            sql += [a for a in args if not a.startswith("-")][1:]
    return sql
