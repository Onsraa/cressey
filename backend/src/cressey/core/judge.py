"""Jev labels one thing for the triangle: is this call needed for the task, given the run
so far? Its answers are cached like the guide models', so the demo replays offline."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, Protocol, Self

import typesafe_sdk
from pydantic import JsonValue
from typesafe_sdk import AsyncTypeSafeClient, Noul, NoulAnswer, RetryPolicy

from cressey.guide.cache import cache_key
from cressey.settings import Settings

QUESTION = "Is this action needed for the task?"  # the wording measured in S2
MODEL = "jev-1.13.0"
Ask = Callable[[dict[str, JsonValue]], Awaitable[float | None]]


class Judge(Protocol):
    async def needed(self, state: dict[str, JsonValue]) -> float | None:
        """Probability the action is needed for the task; None when Jev can't answer."""
        ...


def jev_ask(client: AsyncTypeSafeClient) -> Ask:
    async def ask(state: dict[str, JsonValue]) -> float | None:
        try:
            r = await client.system_one(
                state, questions={"needed": Noul(instructions=QUESTION)}, model=MODEL
            )
        except typesafe_sdk.TypeSafeError:
            return None
        answer = r.answers.get("needed")
        return float(answer.noul) if isinstance(answer, NoulAnswer) else None

    return ask


class JevJudge:
    def __init__(
        self,
        ask: Ask | None,
        mode: Literal["live", "record", "replay", "fallback"],
        cache_dir: Path,
    ) -> None:
        self.ask, self.mode, self.dir = ask, mode, cache_dir

    @classmethod
    def from_settings(cls, s: Settings) -> Self:
        key = s.typesafe_api_key
        client = (
            AsyncTypeSafeClient(
                api_key=key.get_secret_value(),
                timeout=5,
                retry=RetryPolicy(max_retries=1),
            )
            if key
            else None
        )
        return cls(
            jev_ask(client) if client else None, s.model_mode, s.cache_dir / "judge"
        )

    async def needed(self, state: dict[str, JsonValue]) -> float | None:
        path = (
            self.dir / f"{cache_key('judge', MODEL, QUESTION, {'state': state})}.json"
        )
        recorded = float(json.loads(path.read_text())) if path.exists() else None
        if self.mode == "replay":
            return recorded
        live = await self.ask(state) if self.ask else None
        if live is None:
            return recorded if self.mode == "fallback" else None
        if self.mode == "record":
            self.dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(live))
        return live
