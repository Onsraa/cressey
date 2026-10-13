"""What the floor holds whatever the mandate: a call that carries a trap key (held when it
changes something, flagged when it only reads), and a call aimed at Cressey itself."""

import re
from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

from pydantic import JsonValue

from cressey.domain.policy import ToolRule
from cressey.domain.reasons import Reason
from cressey.engine.floor.rules import edits_a_file
from cressey.scan.trace import decoded, strings

# A host and port a call names: in a URL (its port, else its scheme's), or bare, host:port.
ORIGIN = re.compile(
    r"(?P<scheme>https?|wss?)://(?P<host>\[[0-9A-Fa-f:.]+\]|[\w.-]+)(?::(?P<port>\d{1,5}))?"
    r"|(?P<bare>\[[0-9A-Fa-f:.]+\]|[\w.-]+):(?P<bare_port>\d{1,5})\b"
)
DEFAULT_PORTS = {"http": 80, "ws": 80, "https": 443, "wss": 443}


def trap(args: Mapping[str, JsonValue], decoys: Mapping[str, str]) -> Reason | None:
    """Why the safety floor holds a call that carries a trap key, whatever the mandate: in any
    argument, in any case, or in a token that decodes from base64, hex or URL encoding."""
    text = " ".join(s for value in args.values() for s in strings(value))
    forms = [form.lower() for form in (text, *decoded(text))]
    used = [
        name for name, key in decoys.items() if any(key.lower() in f for f in forms)
    ]
    return Reason(check="trap_key", target=", ".join(used)) if used else None


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


def at_cressey(
    rule: ToolRule | None,
    args: Mapping[str, JsonValue],
    guarded: Iterable[tuple[str, int]],
) -> Reason | None:
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
            return Reason(check="self_call")
    return None
