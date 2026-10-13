"""What a curl or wget call does, as code reads it: a read unless it uploads, writes a file, or
sends a body or method that isn't a GraphQL query's."""

import json
import re

from cressey.domain.runs import Risk

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


def http_risk(words: list[str]) -> Risk:
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
