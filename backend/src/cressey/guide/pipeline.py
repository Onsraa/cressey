"""Incident → sourced English fix guide. Models read and write text; code decides what is kept."""

import uuid
from typing import Protocol

from cressey.domain.guides import (
    Guide,
    GuideDraft,
    GuideIncident,
    GuideStep,
    Unit,
    WhyAnswer,
)
from cressey.guide.clients import GuideWriter, QueryRewriter, Reranker, incident_text
from cressey.guide.quotes import verify_quote
from cressey.llm.clients import ModelUnavailable

MSG_NO_SOURCE = (
    "I don't know: no reliable source covers this case. Ask the security team."
)
MSG_NO_STEP = "I don't know: no step could be sourced. Ask the security team."
MSG_UNAVAILABLE = "Guide unavailable: the models aren't answering. Sources found below."
MAX_STEPS = 4


class Searcher(Protocol):
    def search(self, queries: list[str], k: int = 8, top: int = 8) -> list[Unit]: ...


class GuidePipeline:
    def __init__(
        self,
        retriever: Searcher,
        rewriter: QueryRewriter,
        reranker: Reranker,
        writer: GuideWriter,
        relevance_min: float = 0.4,
    ) -> None:
        self.retriever, self.rewriter, self.reranker, self.writer = (
            retriever,
            rewriter,
            reranker,
            writer,
        )
        self.relevance_min = relevance_min

    def keep(self, question: str, units: list[Unit]) -> list[Unit]:
        scores = self.reranker.relevance(question, units)
        kept = [u for u in units if scores.get(u.id, 0.0) >= self.relevance_min]
        return sorted(kept, key=lambda u: -scores[u.id])

    @staticmethod
    def _verified(draft: GuideDraft, kept: list[Unit]) -> tuple[list[GuideStep], int]:
        by_id = {u.id: u for u in kept}
        steps = [
            GuideStep(
                action=s.action,
                source_id=s.source_id,
                quote=s.quote,
                source_title=by_id[s.source_id].title,
            )
            for s in draft.steps
            if s.source_id in by_id and verify_quote(s.quote, by_id[s.source_id])
        ]
        return steps[:MAX_STEPS], len(draft.steps) - len(steps)

    def run(self, incident: GuideIncident) -> Guide:
        gid, raw = uuid.uuid4().hex, incident_text(incident)

        def guide(status, message, steps=(), passages=(), dropped=0) -> Guide:
            return Guide(
                id=gid,
                incident_id=incident.id,
                status=status,
                message=message,
                steps=list(steps),
                passages=list(passages),
                dropped_steps=dropped,
            )

        try:
            fr, en = self.rewriter.rewrite_incident(incident)
        except ModelUnavailable:
            return guide(
                "unavailable", MSG_UNAVAILABLE, passages=self.retriever.search([raw])
            )
        found = self.retriever.search([fr, en, raw])
        try:
            kept = self.keep(fr, found)
            if not kept:
                return guide("unsure", MSG_NO_SOURCE, passages=found)
            draft = self.writer.write(incident, kept)
        except ModelUnavailable:
            return guide("unavailable", MSG_UNAVAILABLE, passages=found)
        steps, dropped = self._verified(draft, kept)
        if not steps:
            return guide("unsure", MSG_NO_STEP, passages=kept, dropped=dropped)
        return guide("ok", None, steps=steps, passages=kept, dropped=dropped)

    def why(self, guide: Guide, question: str) -> WhyAnswer:
        try:
            fr, _ = self.rewriter.rewrite_question(question)
            kept = self.keep(fr, guide.passages)
            if not kept:
                return WhyAnswer(text=MSG_NO_SOURCE, citations=[], status="unsure")
            draft = self.writer.answer(question, kept)
        except ModelUnavailable:
            return WhyAnswer(text=MSG_UNAVAILABLE, citations=[], status="unavailable")
        steps, _ = self._verified(draft, kept)
        if not steps:
            return WhyAnswer(text=MSG_NO_STEP, citations=[], status="unsure")
        return WhyAnswer(
            text="\n".join(s.action for s in steps), citations=steps, status="ok"
        )
