"""Find the secrets a tool result exposes, and hide their values.

detect-secrets recognises URL credentials, keyword assignments and vendor tokens.
A naming rule adds the variables it misses (`API_KEY=...`). A secret is identified by a
fingerprint of its value, so the value itself is never stored.
"""

import hashlib
import re
import threading
from collections.abc import Mapping

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings
from pydantic import BaseModel

from cressey.core.trace import encoded

MIN_VALUE = 8
_NAMED = "Named secret"

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


class Secret(BaseModel):
    kind: str  # detect-secrets plugin name, or "Named secret" for the naming rule
    name: str | None  # the variable name, when the naming rule matched
    fingerprint: str  # first 12 hex chars of sha256(value)
    line: int  # 1-based


def _encodable(text: str) -> str:
    """A lone surrogate (a JSON `\\ud800` escape makes one) cannot be hashed: it raises."""
    return re.sub(r"[\ud800-\udfff]", "\ufffd", text)


def _secret(kind: str, name: str | None, value: str, line: int) -> Secret:
    fingerprint = hashlib.sha256(value.encode()).hexdigest()[:12]
    return Secret(kind=kind, name=name, fingerprint=fingerprint, line=line)


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


def _line_hits(number: int, line: str) -> dict[str, Secret]:
    names = _named(line)
    found: dict[str, Secret] = {}
    for potential in scan_line(line):
        if value := potential.secret_value:
            secret = _secret(potential.type, names.get(value), value, number)
            found.setdefault(value, secret)
    for value, name in names.items():
        found.setdefault(value, _secret(_NAMED, name, value, number))
    return found


def _hits(text: str) -> list[tuple[str, Secret]]:
    """Each (value, Secret) once per distinct value on a line."""
    hits: list[tuple[str, Secret]] = []
    with _LOCK, default_settings() as settings:
        settings.disable_plugins(*_ENTROPY_PLUGINS)
        for number, line in enumerate(text.splitlines(), start=1):
            hits += _line_hits(number, line).items()
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
    markers = {value: f"[secret:{fp}]" for value, fp in (known or {}).items()}
    markers |= {value: f"[secret:{s.fingerprint}]" for value, s in _hits(text)}
    if not markers:
        return text
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
