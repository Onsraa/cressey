"""The decision model answers the triangle's typed questions: it labels each step once, then
judges each write against the evidence kept (S9). It speaks the System One API: Jev's, or a
local Strands Decider when its URL is set. Its answers are cached like the guide models',
so the demo replays offline."""

import asyncio
import hashlib
import json
import logging
import weakref
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Literal, Protocol, Self

import typesafe_sdk
from pydantic import JsonValue
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    RetryPolicy,
)

from cressey.guide.cache import cache_key
from cressey.guide.clients import decision_auth
from cressey.settings import Settings

log = logging.getLogger(__name__)

Question = Noul | Choice
# Jev allows 80 requests/s (docs.typesafe.ai, Models). At about 0.25 s a call, 20 in flight
# stay under it: 16 for the judge, 4 for the guides' re-ranker (guide/clients.py).
JUDGE_IN_FLIGHT = 16
# A Noul's probability, or a Choice's probability per option. Recordings made before 10-10
# hold a Choice's picked option alone (str): they still replay until re-recorded.
Answer = float | str | dict[str, float]
Answers = dict[str, Answer]
Ask = Callable[
    [dict[str, JsonValue], Mapping[str, Question]], Awaitable[Answers | None]
]


class TooLarge(Exception):
    """Jev refused the state for its size; the caller splits it. Seen live on 10-10: HTTP 400
    with the body {'detail': {'error_type': 'max_tokens_exceeded'}}."""


def yes(answer: Answer) -> float:
    """A Noul's probability. Answers come back from the API or from cache files on disk,
    so the type is checked here, at the boundary."""
    if isinstance(answer, bool) or not isinstance(answer, int | float):
        raise TypeError(f"a Noul's probability was expected, got {answer!r}")
    return float(answer)


def top(answer: Answer) -> str | None:
    """The option a Choice picked: the most probable one."""
    if isinstance(answer, dict):
        return max(answer, key=lambda k: answer[k]) if answer else None
    return answer if isinstance(answer, str) else None


def dist(answer: Answer) -> dict[str, float]:
    """A Choice's probability per option. A recording made before 10-10 holds the picked
    option alone: it counts as certain."""
    if isinstance(answer, dict):
        return answer
    if isinstance(answer, str):
        return {answer: 1.0}
    raise TypeError(f"a Choice's probabilities were expected, got {answer!r}")


class NotRecorded(Exception):
    """Replay mode, and no recorded answer for this state: the decision can't be replayed."""


def _fingerprints(state: dict[str, JsonValue]) -> str:
    """A short hash of each top-level field: shows which one changed since recording,
    without logging any of the run's content."""
    return " ".join(
        f"{k}={hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]}"
        for k, v in state.items()
    )


class Judge(Protocol):
    async def answers(
        self, state: dict[str, JsonValue], questions: Mapping[str, Question]
    ) -> Answers | None:
        """Every question about one state, in one call; None when no model answers.
        Raises TooLarge when the state is too big for the model, and NotRecorded when a
        replay has no recorded answer."""
        ...


def system_one_ask(client: AsyncTypeSafeClient, model: str) -> Ask:
    async def ask(
        state: dict[str, JsonValue], questions: Mapping[str, Question]
    ) -> Answers | None:
        try:
            r = await client.system_one(state, questions=dict(questions), model=model)
        except typesafe_sdk.TypeSafeBadRequestError as e:
            if "max_tokens_exceeded" in str(e.body):
                raise TooLarge from e
            return None
        except typesafe_sdk.TypeSafeError:
            return None
        out: Answers = {}
        for name, a in r.answers.items():
            if isinstance(a, NoulAnswer):
                out[name] = float(a.noul)
            elif isinstance(a, ChoiceAnswer):
                out[name] = {k: float(v) for k, v in a.probabilities.items()}
        return out if out.keys() == questions.keys() else None

    return ask


class JevJudge:
    def __init__(
        self,
        ask: Ask | None,
        mode: Literal["live", "record", "replay", "fallback", "replay-first"],
        cache_dir: Path,
        model: str,
    ) -> None:
        self.ask, self.mode, self.dir, self.model = ask, mode, cache_dir, model
        # One cap per event loop: replays serve fresh apps on their own loops with this judge.
        self._slots: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Semaphore
        ] = weakref.WeakKeyDictionary()

    def _in_flight(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        return self._slots.setdefault(loop, asyncio.Semaphore(JUDGE_IN_FLIGHT))

    @classmethod
    def from_settings(cls, s: Settings) -> Self:
        auth = decision_auth(s)
        client = (
            AsyncTypeSafeClient(
                api_key=auth[0],
                base_url=auth[1],
                timeout=5,
                retry=RetryPolicy(max_retries=1),
            )
            if auth
            else None
        )
        ask = system_one_ask(client, s.decision_model) if client else None
        return cls(ask, s.model_mode, s.cache_dir / "judge", s.decision_model)

    async def answers(
        self, state: dict[str, JsonValue], questions: Mapping[str, Question]
    ) -> Answers | None:
        asked = json.dumps(
            {n: q.model_dump() for n, q in questions.items()}, sort_keys=True
        )
        path = (
            self.dir / f"{cache_key('judge', self.model, asked, {'state': state})}.json"
        )
        recorded: Answers | None = (
            json.loads(path.read_text()) if path.exists() else None
        )
        if self.mode in ("replay", "replay-first"):
            if recorded is not None:
                return recorded
            # On stage a miss means the state changed after recording: say which field.
            log.error(
                "judge: no recorded answer %s (%s)", path.name, _fingerprints(state)
            )
            if self.mode == "replay":
                raise NotRecorded(path.name)
        live = None
        if self.ask:
            async with self._in_flight():
                live = await self.ask(state, questions)
        if live is None:
            return recorded if self.mode == "fallback" else None
        if self.mode == "record":
            self.dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(live))
        return live
