"""Find the secrets a tool result exposes, and hide their values.

detect-secrets recognises URL credentials, keyword assignments and vendor tokens.
A naming rule adds the variables it misses (`API_KEY=...`). A secret is identified by a
fingerprint of its value, so the value itself is never stored.

detect-secrets' regexes are quadratic in a line's length on crafted input ("password" × 2 KB
takes 0.25 s, × 16 KB 15 s), and they hold the GIL, so a thread doesn't spare the event
loop. detect-secrets therefore reads only the first SCAN_LIMIT characters of a text, a long
line in windows; the naming rule, which is linear, reads all of it.
"""

import hashlib
import json
import re
import threading
from collections.abc import Iterator, Mapping

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings
from pydantic import JsonValue

from cressey.domain.runs import Secret
from cressey.scan.trace import encoded

MIN_VALUE = 8
_NAMED = "Named secret"
SCAN_LIMIT = 16_384
# A value up to OVERLAP - MARGIN characters long is whole in some window.
WINDOW = 256
OVERLAP = 128
# In a window that stops before the line does, a value ending this close to the cut may be
# cut short: the next window, which starts OVERLAP characters earlier, sees it whole.
MARGIN = 16

# scan_line is the adhoc `--string` mode: these plugins match every token in it and leave
# the entropy test to the caller.
_ENTROPY_PLUGINS = ("Base64HighEntropyString", "HexHighEntropyString")
# detect-secrets keeps its settings in a process-wide singleton, so concurrent scans
# lose secrets.
_LOCK = threading.Lock()
# `NAME=` or `"name":` where the name holds key, token, secret or password. The lookbehind
# makes a name start only at its first character, which keeps the search linear.
_ASSIGNMENT = re.compile(
    r"""(?<![\w.-])(?P<name>(?=[\w.-]*?(?:key|token|secret|password))[\w.-]+)"""
    r"""["']?\s*[=:]\s*""",
    re.IGNORECASE,
)
_VALUE = re.compile(r""""[^"]*"|'[^']*'|\S+""")


def _encodable(text: str) -> str:
    """A lone surrogate (a JSON `\\ud800` escape makes one) cannot be hashed: it raises."""
    return re.sub(r"[\ud800-\udfff]", "\ufffd", text)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _secret(kind: str, name: str | None, value: str, line: int) -> Secret:
    return Secret(kind=kind, name=name, fingerprint=fingerprint(value), line=line)


def _named(line: str) -> dict[str, str]:
    """Value -> variable name, for each assignment whose name looks secret."""
    found: dict[str, str] = {}
    position = 0
    while head := _ASSIGNMENT.search(line, position):
        position = head.end()
        if value_match := _VALUE.match(line, position):
            value = value_match[0].strip("\"'")
            if len(value) >= MIN_VALUE:
                found[value] = head["name"]
                # A secret's value is not scanned again, or `key=key=key=...` goes quadratic.
                position = value_match.end()
    return found


def _plugin_hits(part: str, cut: bool) -> Iterator[tuple[str, str]]:
    """(kind, value) for each detect-secrets hit in `part`, read in overlapping windows.
    `cut`: the line goes on past `part`."""
    starts = range(0, max(len(part) - OVERLAP, 1), WINDOW - OVERLAP) if part else ()
    for start in starts:
        window = part[start : start + WINDOW]
        cut_short = cut or start + WINDOW < len(part)
        for potential in scan_line(window):
            value = potential.secret_value
            if not value:
                continue
            if cut_short and window.rfind(value) + len(value) > len(window) - MARGIN:
                continue  # may be cut short: the next window sees it whole
            yield potential.type, value


def _line_hits(number: int, line: str, budget: int) -> dict[str, Secret]:
    """`budget`: how many of the line's characters detect-secrets may still read."""
    names = _named(line)
    found: dict[str, Secret] = {}
    for kind, value in _plugin_hits(line[:budget], budget < len(line)):
        found.setdefault(value, _secret(kind, names.get(value), value, number))
    for value, name in names.items():
        found.setdefault(value, _secret(_NAMED, name, value, number))
    return found


def _strings(doc: JsonValue) -> Iterator[str]:
    """Each string or number in a JSON document, quoted and unescaped, after its key when it
    has one, so the naming rule still reads `"password": "..."`."""
    stack: list[tuple[str | None, JsonValue]] = [(None, doc)]
    while stack:  # not recursive: as deep as json.loads parses, it is still read
        key, value = stack.pop()
        if isinstance(value, dict):
            stack += reversed(value.items())
        elif isinstance(value, list):
            stack += ((key, v) for v in reversed(value))
        elif value is not None and not isinstance(value, bool):
            yield f'"{value}"' if key is None else f'"{key}": "{value}"'


def _parts(line: str) -> list[str]:
    """A line holding a JSON object or array, as its strings, each on lines of its own: read
    as text, a value at the end of a string runs into the closing quote, or across an
    escaped newline (a call is scanned dumped, and a tool may return JSON). Any other line
    as it is."""
    if not line.lstrip().startswith(("{", "[")):
        return [line]
    try:
        doc: JsonValue = json.loads(line)
    except (ValueError, RecursionError):
        return [line]
    return [part for string in _strings(doc) for part in string.splitlines()]


def _hits(text: str) -> list[tuple[str, Secret]]:
    """Each (value, Secret) once per distinct value on a line."""
    hits: list[tuple[str, Secret]] = []
    budget = SCAN_LIMIT
    with _LOCK, default_settings() as settings:
        settings.disable_plugins(*_ENTROPY_PLUGINS)
        for number, line in enumerate(text.splitlines(), start=1):
            found: dict[str, Secret] = {}
            for part in _parts(line):
                for value, secret in _line_hits(number, part, budget).items():
                    found.setdefault(value, secret)
                budget = max(0, budget - len(part) - 1)
            hits += found.items()
    return hits


def scan(text: str) -> list[tuple[str, Secret]]:
    """Each secret in `text` with its value, to hide that value elsewhere later.
    Callers keep the values in memory only."""
    return _hits(_encodable(text))


def find_secrets(text: str) -> list[Secret]:
    """The secrets in `text`, once per distinct value on a line. Values are not kept."""
    return [secret for _, secret in scan(text)]


def redact(text: str, known: Mapping[str, str] | None = None) -> str:
    """`text` with each value found in it, and each `known` value (value -> fingerprint),
    wherever it appears, replaced by its marker."""
    text = _encodable(text)
    found = {value: s.fingerprint for value, s in _hits(text)}
    return hide(text, {**(known or {}), **found})


def hide(text: str, known: Mapping[str, str]) -> str:
    """`text` with each `known` value (value -> fingerprint), wherever it appears, encoded
    too, replaced by its marker, without scanning it: for a text whose own secrets are
    already known, such as a call's result, scanned once when it came in."""
    text = _encodable(text)
    markers = {value: f"[secret:{fp}]" for value, fp in known.items()}
    if not markers:
        return text
    # A JSON line escapes a value's quotes and backslashes: that form is hidden too.
    markers |= {json.dumps(v, ensure_ascii=False)[1:-1]: m for v, m in markers.items()}
    # One pass, longest value first: a marker is never rescanned, and a value never
    # cuts a longer one short.
    longest_first = sorted(markers, key=len, reverse=True)
    pattern = re.compile("|".join(map(re.escape, longest_first)))
    out = pattern.sub(lambda match: markers[match[0]], text)
    # Encoded forms too (stress test F3): a token whose base64, hex or URL decoding holds one.
    # A decoding equal to its token decoded nothing (URL text without %): already handled.
    for token, plain in encoded(out):
        value = plain != token and next((v for v in longest_first if v in plain), None)
        if value:
            out = out.replace(token, markers[value])
    return out
