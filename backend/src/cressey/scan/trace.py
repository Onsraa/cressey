"""Find where each value of a dangerous call was first read.

Each token of the call is looked up in what the agent read earlier: as is, in
lower case, and after base64, hex or URL decoding. Values that were reversed,
encrypted or rebuilt from several reads are not traced, by design.
"""

import base64
import re
from collections.abc import Callable, Iterator, Sequence
from urllib.parse import unquote

from pydantic import BaseModel, JsonValue

from cressey.domain.incidents import How

MIN_TOKEN = 8  # shorter tokens match by chance

Reads = Sequence[tuple[int, str]]  # (step, tool output), in step order

_WORD_BREAK = re.compile(r"""[\s"',;()\[\]{}<>]+""")
_PART_BREAK = re.compile(r"[=:&]")
# Strict on purpose: invalid input must fail, not be dropped or repaired.
_DECODERS: tuple[tuple[How, Callable[[str], str]], ...] = (
    ("base64", lambda t: base64.b64decode(t, altchars=b"-_", validate=True).decode()),
    ("hex", lambda t: bytes.fromhex(t).decode()),
    ("url", lambda t: unquote(t, errors="strict")),
)


class Origin(BaseModel):
    token: str  # as it appears in the call
    step: int  # first step whose output contained it
    how: How


def strings(value: JsonValue) -> list[str]:
    """Every string and number in a call's arguments: the trace reads raw values, not JSON."""
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return [] if value is None or isinstance(value, bool) else [str(value)]


def tokens(call: str) -> list[str]:
    # The whole word stays too: base64 padding and URLs contain `=` and `:`.
    tokens = [
        token
        for word in _WORD_BREAK.split(call)
        for token in (word, *_PART_BREAK.split(word))
        if len(token) >= MIN_TOKEN
    ]
    return list(dict.fromkeys(tokens))


# What a word carries at its edges in prose or markdown: a sentence's period, `code`, **bold**.
_EDGES = ".,;:!?`*_~'\"()[]{}<>|"


def index(text: str) -> set[str]:
    """The tokens of `text`, as they are and with their edge punctuation stripped, each also
    lower-cased: what `asked_by` looks a value up in (a token of a call, where `trace` finds
    it anywhere in the text)."""
    forms = {
        f for t in tokens(text) for f in (t, t.strip(_EDGES)) if len(f) >= MIN_TOKEN
    }
    return forms | {f.lower() for f in forms}


def _decodings(token: str) -> Iterator[tuple[How, str]]:
    """What `token` decodes to in each encoding it is valid in, when that's printable text."""
    for how, decode in _DECODERS:
        try:
            text = decode(token)
        except ValueError:  # not encoded this way; binascii.Error is a ValueError
            continue
        if len(text) >= MIN_TOKEN and text.isprintable():
            yield how, text


def encoded(text: str) -> list[tuple[str, str]]:
    """(token, what it decodes to) for each token of `text` valid as base64, hex or URL."""
    return [(token, d) for token in tokens(text) for _, d in _decodings(token)]


def decoded(text: str) -> list[str]:
    """What the tokens of `text` decode to as base64, hex or URL encoding."""
    return [d for _, d in encoded(text)]


def _lookups(
    token: str, reads: Reads, lowered: Reads
) -> Iterator[tuple[How, str, Reads]]:
    """What to look for and where, in the order to try it."""
    yield "exact", token, reads
    yield "lowercase", token.lower(), lowered
    for how, text in _decodings(token):
        yield how, text.lower(), lowered


def _first_step(needle: str, texts: Reads) -> int | None:
    return min((step for step, text in texts if needle in text), default=None)


def _origin(token: str, reads: Reads, lowered: Reads) -> Origin | None:
    for how, needle, texts in _lookups(token, reads, lowered):
        step = _first_step(needle, texts)
        if step is not None:
            return Origin(token=token, step=step, how=how)
    return None


def trace(call: str, reads: Reads) -> list[Origin]:
    """Origin of each token of `call`; `reads` are (step, tool output) in step order."""
    lowered = [(step, text.lower()) for step, text in reads]
    origins = (_origin(token, reads, lowered) for token in tokens(call))
    return [origin for origin in origins if origin is not None]
