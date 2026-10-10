import pytest

from cressey.guide.clients import ModelUnavailable
from cressey.guide.models import DraftStep, Guide, GuideDraft, GuideIncident, Unit
from cressey.guide.pipeline import GuidePipeline

R9 = Unit(
    id="anssi-fr:R9",
    source="anssi",
    lang="fr",
    title="R9 Proscrire l'usage automatisé",
    text="Un système d’IA doit être configuré de manière à ne pas être en mesure d’exécuter des actions critiques.",
)
R12 = Unit(
    id="anssi-fr:R12",
    source="anssi",
    lang="fr",
    title="R12",
    text="Cloisonner chaque phase du système d'IA.",
)
INC = GuideIncident(
    id="i1",
    leg="opportunity",
    owner_role="key_owner",
    summary="clé lue",
    source=".env.prod",
)
GOOD = DraftStep(
    action="Bloquer",
    source_id="anssi-fr:R9",
    quote="doit être configuré de manière à ne pas être en mesure",
)


class Retr:
    def __init__(self, units):
        self.units, self.queries = units, []

    def search(self, queries: list[str], k: int = 8, top: int = 8) -> list[Unit]:
        self.queries.append(queries)
        return self.units


class Rew:
    def __init__(self, fail=False):
        self.fail = fail

    def rewrite_incident(self, incident: GuideIncident) -> tuple[str, str]:
        if self.fail:
            raise ModelUnavailable("x")
        return ("fr", "en")

    def rewrite_question(self, question: str) -> tuple[str, str]:
        return ("fr", "en")


class Rer:
    def __init__(self, score=0.9, fail=False):
        self.score, self.fail = score, fail

    def relevance(self, question: str, units: list[Unit]) -> dict[str, float]:
        if self.fail:
            raise ModelUnavailable("x")
        return {u.id: self.score for u in units}


class Wri:
    def __init__(self, draft=None, fail=False):
        self.draft, self.fail, self.calls = draft or GuideDraft(steps=[GOOD]), fail, 0

    def write(self, incident: GuideIncident, units: list[Unit]) -> GuideDraft:
        self.calls += 1
        if self.fail:
            raise ModelUnavailable("x")
        return self.draft

    def answer(self, question: str, units: list[Unit]) -> GuideDraft:
        return self.draft


def pipe(
    units=(R9, R12),
    rewriter: Rew | None = None,
    reranker: Rer | None = None,
    writer: Wri | None = None,
):
    return GuidePipeline(
        Retr(list(units)), rewriter or Rew(), reranker or Rer(), writer or Wri()
    )


def test_nothing_relevant_means_no_writer_call_and_unsure():
    w = Wri()
    g = pipe(reranker=Rer(score=0.2), writer=w).run(INC)
    assert g.status == "unsure" and g.steps == [] and w.calls == 0
    assert g.message and g.message.startswith("Je ne sais pas : aucune source fiable")


def test_steps_citing_unprovided_units_or_invented_quotes_are_dropped():
    bad_src = DraftStep(action="x", source_id="runbook:x", quote=GOOD.quote)
    bad_quote = DraftStep(
        action="y",
        source_id="anssi-fr:R9",
        quote="texte inventé de huit mots au moins ici présent",
    )
    g = pipe(writer=Wri(GuideDraft(steps=[GOOD, bad_src, bad_quote]))).run(INC)
    assert [s.source_id for s in g.steps] == ["anssi-fr:R9"] and g.dropped_steps == 2
    assert g.steps[0].source_title == R9.title and g.status == "ok"


def test_all_steps_dropped_means_unsure():
    bad = DraftStep(action="x", source_id="runbook:x", quote=GOOD.quote)
    g = pipe(writer=Wri(GuideDraft(steps=[bad]))).run(INC)
    assert (
        g.status == "unsure"
        and g.message
        and g.message.startswith("Je ne sais pas : aucune étape")
    )


def test_writer_down_returns_passages_and_unavailable():
    g = pipe(writer=Wri(fail=True)).run(INC)
    assert g.status == "unavailable" and g.passages
    assert g.message and g.message.startswith("Guide indisponible")


@pytest.mark.parametrize("which", ["rewriter", "reranker"])
def test_other_model_failures_are_unavailable_not_crashes(which):
    kw = (
        {"rewriter": Rew(fail=True)}
        if which == "rewriter"
        else {"reranker": Rer(fail=True)}
    )
    g = pipe(**kw).run(INC)
    assert g.status == "unavailable" and g.passages


def test_rewriter_down_still_searches_with_raw_text():
    r = Retr([R9])
    GuidePipeline(r, Rew(fail=True), Rer(), Wri()).run(INC)
    assert r.queries and "clé lue" in r.queries[0][0]


def test_search_uses_both_rewrites_and_raw_text():
    r = Retr([R9])
    GuidePipeline(r, Rew(), Rer(), Wri()).run(INC)
    assert r.queries[0][:2] == ["fr", "en"] and "clé lue" in r.queries[0][2]


def test_at_most_four_steps():
    assert len(pipe(writer=Wri(GuideDraft(steps=[GOOD] * 6))).run(INC).steps) == 4


def test_why_uses_only_the_guide_passages():
    guide = Guide(
        id="g",
        incident_id="i1",
        status="ok",
        message=None,
        steps=[],
        passages=[R9],
        dropped_steps=0,
    )
    out_of_guide = DraftStep(
        action="z",
        source_id="anssi-fr:R12",
        quote="Cloisonner chaque phase du système d'IA x y z",
    )
    a = pipe(writer=Wri(GuideDraft(steps=[GOOD, out_of_guide]))).why(
        guide, "Pourquoi je ne peux pas garder la clé ?"
    )
    assert [c.source_id for c in a.citations] == ["anssi-fr:R9"] and a.status == "ok"
