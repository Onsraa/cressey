"""Find where each value of a dangerous call was first read.

Each token of the call is looked up in what the agent read earlier: as is, in
lower case, and after base64, hex or URL decoding. Values that were reversed,
encrypted or rebuilt from several reads are not traced, by design.
"""

import base64
import re
from collections.abc import Callable, Iterator, Sequence
from typing import Literal
from urllib.parse import unquote

from pydantic import BaseModel

MIN_TOKEN = 8  # shorter tokens match by chance

How = Literal["exact", "lowercase", "base64", "hex", "url"]
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


def _tokens(call: str) -> list[str]:
    # The whole word stays too: base64 padding and URLs contain `=` and `:`.
    tokens = [
        token
        for word in _WORD_BREAK.split(call)
        for token in (word, *_PART_BREAK.split(word))
        if len(token) >= MIN_TOKEN
    ]
    return list(dict.fromkeys(tokens))


def _lookups(
    token: str, reads: Reads, lowered: Reads
) -> Iterator[tuple[How, str, Reads]]:
    """What to look for and where, in the order to try it."""
    yield "exact", token, reads
    yield "lowercase", token.lower(), lowered
    for how, decode in _DECODERS:
        try:
            text = decode(token)
        except ValueError:  # not encoded this way; binascii.Error is a ValueError
            continue
        if len(text) >= MIN_TOKEN and text.isprintable():
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
    origins = (_origin(token, reads, lowered) for token in _tokens(call))
    return [origin for origin in origins if origin is not None]
