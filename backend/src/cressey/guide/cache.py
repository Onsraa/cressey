"""Record-and-replay cache for every model call, so the demo survives a network outage.

live: call, store nothing · record: call and store · replay: cache only, never the network
fallback: call; if the model is unavailable, serve the stored answer (mode for the stage)
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import numpy as np

from cressey.guide.clients import (
    PROMPT_GUIDE_V1,
    PROMPT_REWRITE_INCIDENT_V1,
    PROMPT_REWRITE_QUESTION_V1,
    PROMPT_WHY_V1,
    JevReranker,
    ModelUnavailable,
    OpenAIEmbedder,
    OpenAIRewriter,
    OpenAIWriter,
)
from cressey.guide.models import GuideDraft, GuideIncident, Unit
from cressey.settings import Settings

Mode = Literal["live", "record", "replay", "fallback"]


def cache_key(
    adapter: str, model: str, prompt_version: str, payload: dict[str, Any]
) -> str:
    blob = json.dumps(
        [adapter, model, prompt_version, payload], sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _seen(incident: GuideIncident) -> dict:
    """The incident as the model sees it: the id never reaches it, so a new id still replays."""
    return incident.model_dump(exclude={"id"})


def _units(units: list[Unit]) -> list[list[str]]:
    return [[u.id, u.text] for u in units]


def _version(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


class Cached:
    """Wraps any adapter (Embedder, QueryRewriter, Reranker, GuideWriter) and exposes the same methods."""

    def __init__(
        self,
        inner: Any,
        adapter: str,
        model: str,
        prompt_version: str,
        mode: Mode,
        cache_dir: Path,
    ):
        self.inner, self.adapter, self.model, self.version, self.mode = (
            inner,
            adapter,
            model,
            prompt_version,
            mode,
        )
        self.dir = cache_dir / adapter

    def _call(
        self,
        method: str,
        payload: dict[str, Any],
        live: Callable[[], Any],
        encode,
        decode,
    ) -> Any:
        path = (
            self.dir
            / f"{cache_key(self.adapter + '.' + method, self.model, self.version, payload)}.json"
        )

        def stored() -> Any:
            if not path.exists():
                raise ModelUnavailable(f"not in cache: {self.adapter}.{method}")
            return decode(json.loads(path.read_text()))

        if self.mode == "replay":
            return stored()
        try:
            out = live()
        except ModelUnavailable:
            if self.mode == "fallback":
                return stored()
            raise
        if self.mode == "record":
            self.dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(encode(out), ensure_ascii=False))
        return out

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._call(
            "embed",
            {"texts": texts},
            lambda: self.inner.embed(texts),
            lambda v: v.tolist(),
            np.array,
        )

    def rewrite_incident(self, incident: GuideIncident) -> tuple[str, str]:
        return self._call(
            "rewrite_incident",
            _seen(incident),
            lambda: self.inner.rewrite_incident(incident),
            list,
            tuple,
        )

    def rewrite_question(self, question: str) -> tuple[str, str]:
        return self._call(
            "rewrite_question",
            {"q": question},
            lambda: self.inner.rewrite_question(question),
            list,
            tuple,
        )

    def relevance(self, question: str, units: list[Unit]) -> dict[str, float]:
        payload = {"q": question, "units": _units(units)}
        return self._call(
            "relevance",
            payload,
            lambda: self.inner.relevance(question, units),
            dict,
            dict,
        )

    def write(self, incident: GuideIncident, units: list[Unit]) -> GuideDraft:
        payload = {"incident": _seen(incident), "units": _units(units)}
        return self._call(
            "write",
            payload,
            lambda: self.inner.write(incident, units),
            GuideDraft.model_dump,
            GuideDraft.model_validate,
        )

    def answer(self, question: str, units: list[Unit]) -> GuideDraft:
        payload = {"q": question, "units": _units(units)}
        return self._call(
            "answer",
            payload,
            lambda: self.inner.answer(question, units),
            GuideDraft.model_dump,
            GuideDraft.model_validate,
        )


def wrap_all(s: Settings) -> tuple[Cached, Cached, Cached, Cached]:
    def c(inner: Any, adapter: str, model: str, version: str) -> Cached:
        return Cached(inner, adapter, model, version, s.model_mode, s.cache_dir)

    rewrite_v = _version(PROMPT_REWRITE_INCIDENT_V1 + PROMPT_REWRITE_QUESTION_V1)
    writer_v = _version(PROMPT_GUIDE_V1 + PROMPT_WHY_V1)
    return (
        c(OpenAIEmbedder.from_settings(s), "embedder", s.embedding_model, "v1"),
        c(OpenAIRewriter.from_settings(s), "rewriter", s.rewrite_model, rewrite_v),
        c(JevReranker.from_settings(s), "reranker", "jev-1.13.0", "v1"),
        c(OpenAIWriter.from_settings(s), "writer", s.writer_model, writer_v),
    )
