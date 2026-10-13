"""The guide pipeline's models through the record-and-replay cache (llm/cache.py): each
method keyed by what its model reads."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from cressey.domain.guides import GuideDraft, GuideIncident, Unit
from cressey.guide.clients import (
    PROMPT_GUIDE_V1,
    PROMPT_REWRITE_INCIDENT_V1,
    PROMPT_REWRITE_QUESTION_V1,
    PROMPT_WHY_V1,
    BedrockEmbedder,
    BedrockReranker,
    JevReranker,
    OpenAIEmbedder,
    OpenAIRewriter,
    OpenAIWriter,
)
from cressey.llm.cache import Cache, Mode, prompt_version
from cressey.settings import Settings


def _seen(incident: GuideIncident) -> dict:
    """The incident as the model sees it: the id never reaches it, so a new id still replays."""
    return incident.model_dump(exclude={"id"})


def _units(units: list[Unit]) -> list[list[str]]:
    return [[u.id, u.text] for u in units]


class Cached:
    """Wraps any adapter (Embedder, QueryRewriter, Reranker, GuideWriter) and exposes the same methods."""

    def __init__(
        self,
        inner: Any,
        adapter: str,
        model: str,
        version: str,
        mode: Mode,
        cache_dir: Path,
    ):
        self.inner, self.adapter, self.model, self.version = (
            inner,
            adapter,
            model,
            version,
        )
        self.cache = Cache(mode, cache_dir / adapter)

    def _call(
        self,
        method: str,
        payload: dict[str, Any],
        live: Callable[[], Any],
        encode: Callable[[Any], Any],
        decode: Callable[[Any], Any],
    ) -> Any:
        return self.cache.call(
            f"{self.adapter}.{method}",
            self.model,
            self.version,
            payload,
            live,
            encode,
            decode,
        )

    def embed(self, texts: list[str], query: bool = False) -> np.ndarray:
        return self._call(
            "embed",
            {"texts": texts, "query": query},
            lambda: self.inner.embed(texts, query),
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


def _embedder(s: Settings) -> BedrockEmbedder | OpenAIEmbedder:
    if s.models == "bedrock":
        return BedrockEmbedder.from_settings(s)
    return OpenAIEmbedder.from_settings(s)


def _reranker(s: Settings) -> BedrockReranker | JevReranker:
    if s.reranker == "bedrock":
        return BedrockReranker.from_settings(s)
    return JevReranker.from_settings(s)


def wrap_all(s: Settings) -> tuple[Cached, Cached, Cached, Cached]:
    def c(inner: Any, adapter: str, model: str, version: str) -> Cached:
        return Cached(inner, adapter, model, version, s.model_mode, s.cache_dir)

    rewrite_v = prompt_version(PROMPT_REWRITE_INCIDENT_V1 + PROMPT_REWRITE_QUESTION_V1)
    writer_v = prompt_version(PROMPT_GUIDE_V1 + PROMPT_WHY_V1)
    return (
        c(_embedder(s), "embedder", s.embedding_model, "v1"),
        c(OpenAIRewriter.from_settings(s), "rewriter", s.rewrite_model, rewrite_v),
        c(_reranker(s), "reranker", s.rerank_model, "v1"),
        c(OpenAIWriter.from_settings(s), "writer", s.writer_model, writer_v),
    )
