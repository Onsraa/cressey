"""Who asked for an act (the core design's I4), read by code from where its values came: a
value the task names, one the user typed, one the agent read in a tool's result. An act none
of whose values came from elsewhere is the agent's own. The values are traced as the incident
sources are (scan/trace.py): tokens long enough not to match by chance."""

from collections.abc import Mapping

from pydantic import JsonValue

from cressey.domain.acts import Asker
from cressey.domain.runs import Run
from cressey.scan.trace import strings, trace


def asked_by(run: Run, args: Mapping[str, JsonValue]) -> list[Asker]:
    """For the run so far: call it before the act's own step is added."""
    values = " ".join(s for v in args.values() for s in strings(v))
    prompts = [(m.after, m.text) for m in run.messages if m.role == "user"]
    results = [(s.n, s.result) for s in run.steps if s.result]
    sources: list[tuple[Asker, list[tuple[int, str]]]] = [
        ("task", [(0, run.task)]),
        ("user", prompts),
        ("content", results),
    ]
    found: list[Asker] = [who for who, texts in sources if trace(values, texts)]
    return found or ["agent"]
