import json

from cressey.domain.guides import DraftStep, GuideDraft
from cressey.guide.eval import evaluate, same_unit
from cressey.guide.pipeline import GuidePipeline
from tests.guide.test_pipeline import GOOD, R9, R12, Rer, Retr, Rew, Wri


class BM25Stub:
    """Exposes the BM25-only list the harness compares against."""

    def __init__(self, ids):
        self.ids = ids

    def bm25_top(self, q, k):
        return self.ids


def test_same_unit_treats_fr_and_en_recommendations_as_equal():
    assert same_unit("anssi-fr:R9", "anssi-en:R9") and not same_unit(
        "anssi-fr:R9", "anssi-fr:R12"
    )


def test_report_counts_exact_hits_citations_and_unsure(tmp_path):
    rset = tmp_path / "r.json"
    rset.write_text(
        json.dumps(
            [
                {
                    "q": "a",
                    "lang": "fr",
                    "expected": ["anssi-en:R9"],
                    "split": "dev",
                },  # twin of R9 → hit
                {
                    "q": "b",
                    "lang": "fr",
                    "expected": ["runbook:x"],
                    "split": "dev",
                },  # miss
                {
                    "q": "c",
                    "lang": "fr",
                    "expected": [],
                    "split": "dev",
                },  # out of scope, kept non-empty → wrong
                {
                    "q": "d",
                    "lang": "fr",
                    "expected": ["anssi-fr:R9"],
                    "split": "heldout",
                },  # other split, ignored
            ]
        )
    )
    iset = tmp_path / "i.json"
    iset.write_text(
        json.dumps(
            [
                {
                    "id": "i1",
                    "leg": "opportunity",
                    "owner_role": "key_owner",
                    "summary": "s",
                    "source": "x",
                    "split": "dev",
                },
            ]
        )
    )
    bad = DraftStep(action="x", source_id="runbook:x", quote=GOOD.quote)
    pipe = GuidePipeline(
        Retr([R9, R12]), Rew(), Rer(), Wri(GuideDraft(steps=[GOOD, GOOD, GOOD, bad]))
    )
    rep = evaluate(pipe, BM25Stub(["anssi-fr:R12"]), rset, iset, "dev")
    assert (
        rep.n_questions == 2
        and rep.hit_at_3_reranked == 0.5
        and rep.hit_at_3_bm25 == 0.0
    )
    assert rep.unsure_correct == 0 and rep.n_out_of_scope == 1
    assert rep.citation_validity == 0.75 and rep.n_incidents == 1


class ScoredRer:
    """A re-ranker with one fixed score per passage."""

    def __init__(self, scores: dict[str, float]):
        self.scores = scores

    def relevance(self, question, units):
        return {u.id: self.scores[u.id] for u in units}


def test_calibration_counts_what_each_threshold_keeps(tmp_path):
    from cressey.guide.eval import calibrate

    rset = tmp_path / "r.json"
    rset.write_text(
        json.dumps(
            [
                {"q": "a", "lang": "fr", "expected": ["anssi-en:R9"], "split": "dev"},
                {"q": "c", "lang": "fr", "expected": [], "split": "dev"},
            ]
        )
    )
    rer = ScoredRer({R9.id: 0.8, R12.id: 0.3})
    pipe = GuidePipeline(Retr([R9, R12]), Rew(), rer, Wri())
    rows = {r.threshold: r for r in calibrate(pipe, rset, "dev", [0.2, 0.5])}
    high, low = rows[0.5], rows[0.2]
    assert (high.expected_kept, high.expected_total) == (1, 1)
    assert (high.others_kept, high.others_total, low.others_kept) == (0, 1, 1)
    assert high.out_of_scope_answered == 1 and high.out_of_scope_total == 1
