"""The agent's words cut into thoughts, and the objects each thought names.

A message is split where a thought ends: at a sentence end, a line break or a list item.
A sentence that opens with a turn ("However", "Mais") is the other side of the one before it,
so it stays in that thought. The objects are the ids a thought can share with a call or a
secret: that is how a thought is tied to what the agent did.
"""

import re

from pydantic import BaseModel

from cressey.core.models import Run
from cressey.core.triangle import SENTENCE, _pieces

TURNS = (
    "However",
    "But",
    "Yet",
    "Still",
    "Nevertheless",
    "Even so",
    "Mais",
    "Cependant",
    "Pourtant",
    "Toutefois",
)
_TURN = re.compile(rf"(?:{'|'.join(map(re.escape, TURNS))})\b", re.IGNORECASE)
# The content of a fenced block (the opening line's language is dropped); an unclosed block
# runs to the end.
_FENCE = re.compile(
    r"^[ \t]*```[^\n]*\n(.*?)(?:^[ \t]*```[ \t]*$|\Z)", re.MULTILINE | re.DOTALL
)
_QUOTE = re.compile(r"^(?:>\s*)+")
_ITEM = re.compile(r"^(?:[-*]|\d+[.)])\s+")
_INLINE = re.compile(r"`([^`\n]+)`")

_HEX = "[0-9a-fA-F]"
_PATH = r"[\w.~$@%+-]"
# One match per object, leftmost first; at the same spot the earlier alternative wins.
_OBJECT = re.compile(
    r"|".join(
        [
            r"`(?P<span>[^`\n]+)`",
            r"\[secret:(?P<marker>[0-9a-f]+)\]",
            # A URL stops where a marker starts: the marker is its own object.
            r"(?P<url>[a-zA-Z][a-zA-Z0-9+.-]*://(?:(?!\[secret:)[^\s`<>\"')\]])+)",
            # A token with a slash and a word character in it, cut before any punctuation
            # that is not part of a name. It cannot start right after a marker (`]`): that
            # is the tail of a URL or path the marker cut.
            rf"(?<![\w.~$@%+/\]-])(?=[\w.~$@%+/-]*\w)(?P<path>{_PATH}*(?:/{_PATH}*)+)",
            r"\$\{?(?P<dollar>[A-Za-z_]\w*)",
            r"\b(?P<assign>[A-Z_][A-Z0-9_]*)=(?!=)",
            rf"\b(?P<id>{_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{12}}|{_HEX}{{8,}})\b",
        ]
    )
)


class Segment(BaseModel):
    text: str
    quoted: bool = False  # a line the agent quoted rather than said
    code: list[
        str
    ] = []  # the inline spans in the text, then the fenced blocks after it


def segment(text: str) -> list[Segment]:
    built: list[Segment] = []  # `code` holds only the fenced blocks until the end
    for i, chunk in enumerate(_FENCE.split(text)):
        if i % 2:  # a fenced block is not a thought; it belongs to the one before
            if built and chunk.strip():
                built[-1].code.append(chunk.strip())
            continue
        for line in chunk.splitlines():
            line = line.strip()
            quoted = line.startswith(">")
            line = _ITEM.sub("", _QUOTE.sub("", line)).strip()
            for sentence in map(str.strip, SENTENCE.split(line)):
                if not any(c.isalnum() for c in sentence):
                    continue
                if built and built[-1].quoted == quoted and _TURN.match(sentence):
                    built[-1].text += f" {sentence}"
                else:
                    built.append(Segment(text=sentence, quoted=quoted))
    segments: list[Segment] = []
    for thought in built:
        pieces = _pieces(thought.text)
        segments += [
            Segment(text=p, quoted=thought.quoted, code=_INLINE.findall(p))
            for p in pieces
        ]
        segments[-1].code += thought.code
    return segments


def objects(text: str, code: list[str], run: Run) -> list[str]:
    """The ids `text` and its `code` name, once each, in the order they first appear. A
    variable named like a secret the run has read stands for that secret, as does its marker."""
    secrets: dict[str, str] = {}
    for s in run.steps:
        for secret in s.secrets:
            if secret.name:
                secrets.setdefault(secret.name, f"secret:{secret.fingerprint}")
    found: dict[str, None] = {}
    for part in (text, *code):
        for m in _OBJECT.finditer(part):
            kind, value = next(
                (k, v) for k, v in m.groupdict().items() if v is not None
            )
            if kind == "marker":
                found[f"secret:{value}"] = None
            elif kind in ("dollar", "assign"):
                found[secrets.get(value, value)] = None
            elif kind in ("url", "path"):
                found[value.rstrip(".,;:!?")] = None
            else:
                found[value.strip()] = None
    return list(found)
