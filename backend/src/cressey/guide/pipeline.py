"""Incident → sourced French fix guide. Models read and write text; code decides what is kept."""

import uuid
from typing import Protocol

from cressey.guide.clients import (
    GuideWriter,
    ModelUnavailable,
    QueryRewriter,
    Reranker,
    incident_text,
)
from cressey.guide.models import (
    Guide,
    GuideDraft,
    GuideIncident,
    GuideStep,
    Unit,
    WhyAnswer,
)
from cressey.guide.quotes import verify_quote

MSG_NO_SOURCE = (
    "Je ne sais pas : aucune source fiable ne couvre ce cas. Voir l'équipe sécurité."
)
MSG_NO_STEP = (
    "Je ne sais pas : aucune étape n'a pu être sourcée. Voir l'équipe sécurité."
)
MSG_UNAVAILABLE = (
    "Guide indisponible : les modèles ne répondent pas. Sources trouvées ci-dessous."
)
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
