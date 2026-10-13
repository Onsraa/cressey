"""Who asked for an act (the core design's I4), read by code from where its values came: a
value the task names, one the user typed, one the agent read in a tool's result. An act none
of whose values came from elsewhere is the agent's own. A value is a token long enough not to
match by chance (scan/trace.py), as it is, lower-cased, or decoded from base64, hex or URL."""

from collections.abc import Mapping

from pydantic import JsonValue

from cressey.domain.acts import Asker
from cressey.domain.runs import Run
from cressey.scan.trace import encoded, index, strings


def _forms(values: str) -> set[str]:
    """Each token of the call as it is and lower-cased, and what each decodes to."""
    plain = [text for _, text in encoded(values)]
    decoded = {form for text in plain for form in index(text)}
    return index(values) | decoded | {text.lower() for text in plain}


def asked_by(run: Run, args: Mapping[str, JsonValue]) -> list[Asker]:
    """For the run so far: call it before the act's own step is added. Each result joins the
    run's index once, so a call costs its own values, not all the run has read."""
    for step in list(run.steps):
        if step.result and step.n not in run.read_indexed:
            run.read_tokens |= index(step.result)
            run.read_indexed.add(step.n)
    wanted = _forms(" ".join(s for v in args.values() for s in strings(v)))
    prompts = " ".join(m.text for m in run.messages if m.role == "user")
    sources: list[tuple[Asker, set[str]]] = [
        ("task", index(run.task)),
        ("user", index(prompts)),
        ("content", run.read_tokens),
    ]
    found: list[Asker] = [who for who, known in sources if wanted & known]
    return found or ["agent"]
