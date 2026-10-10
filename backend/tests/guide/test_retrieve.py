import numpy as np
import pytest

from cressey.guide.clients import ModelUnavailable
from cressey.guide.models import Unit
from cressey.guide.retrieve import Retriever, rrf_fuse


def _u(i: str, text: str) -> Unit:
    return Unit(id=i, source="anssi", lang="fr", title=i, text=text)


UNITS = [
    _u(
        "anssi-fr:R9",
        "Proscrire l'usage automatisé de systèmes d'IA pour des actions critiques sur le SI",
    ),
    _u(
        "anssi-fr:R12",
        "Cloisonner chaque phase du système d'IA dans un environnement dédié",
    ),
    _u(
        "anssi-fr:R29",
        "Journaliser l'ensemble des traitements réalisés au sein du système d'IA",
    ),
    _u(
        "runbook:rotation-des-cles",
        "Révoquer immédiatement la clé exposée dans le gestionnaire de secrets",
    ),
]


class FakeEmbedder:
    """Puts 'validation humaine' next to R9 only, to prove embeddings rescue a lexical miss."""

    model = "fake"
    calls = 0

    def embed(self, texts: list[str]) -> np.ndarray:
        FakeEmbedder.calls += 1
        rows = []
        for t in texts:
            v = np.full(5, 0.01)
            if "validation" in t or "Proscrire" in t:
                v[0] = 1.0
            else:
                v[1 + len(t) % 4] = 1.0
            rows.append(v / np.linalg.norm(v))
        return np.array(rows)


class FailingEmbedder:
    model = "fake"

    def embed(self, texts: list[str]) -> np.ndarray:
        raise ModelUnavailable("down")


class FlakyQueries(FakeEmbedder):
    """Embeds the corpus, then fails on the next query only."""

    fail_next = False

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.fail_next:
            self.fail_next = False
            raise ModelUnavailable("blip")
        return super().embed(texts)


def test_rrf_prefers_items_ranked_high_in_several_lists():
    assert rrf_fuse([["a", "b", "c"], ["b", "a", "d"], ["b", "e"]])[0] == "b"


def test_search_merges_bm25_and_embeddings(tmp_path):
    hits = Retriever(UNITS, FakeEmbedder(), tmp_path / "emb.npy").search(
        ["validation humaine avant une action critique"]
    )
    assert "anssi-fr:R9" in [u.id for u in hits[:3]] and len(hits) <= 8


def test_embedder_failure_falls_back_to_bm25(tmp_path):
    r = Retriever(UNITS, FailingEmbedder(), tmp_path / "emb.npy")
    assert r.search(["cloisonner chaque phase"])[0].id == "anssi-fr:R12"
    assert r.bm25_only


def test_embedding_cache_is_reused_then_rebuilt_when_corpus_changes(tmp_path):
    cache = tmp_path / "emb.npy"
    FakeEmbedder.calls = 0
    Retriever(UNITS, FakeEmbedder(), cache)
    Retriever(UNITS, FakeEmbedder(), cache)
    assert FakeEmbedder.calls == 1
    Retriever([*UNITS, _u("anssi-fr:R1", "nouveau texte")], FakeEmbedder(), cache)
    assert FakeEmbedder.calls == 2


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_query_returns_nothing(tmp_path, q):
    assert Retriever(UNITS, None, tmp_path / "e.npy").search([q]) == []


def test_one_failed_query_embedding_keeps_hybrid_search(tmp_path):
    e = FlakyQueries()
    r = Retriever(UNITS, e, tmp_path / "emb.npy")
    q = ["validation humaine avant une action critique"]
    e.fail_next = True
    r.search(q)
    assert "anssi-fr:R9" in [u.id for u in r.search(q)[:3]]


def test_embedding_cache_is_rebuilt_when_the_model_changes(tmp_path):
    cache = tmp_path / "emb.npy"
    FakeEmbedder.calls = 0
    Retriever(UNITS, FakeEmbedder(), cache)
    other = FakeEmbedder()
    other.model = "other-model"
    Retriever(UNITS, other, cache)
    assert FakeEmbedder.calls == 2


def test_embedding_cache_with_the_wrong_row_count_is_rebuilt(tmp_path):
    cache = tmp_path / "emb.npy"
    FakeEmbedder.calls = 0
    Retriever(UNITS, FakeEmbedder(), cache)
    np.save(cache, np.load(cache)[:-1])
    Retriever(UNITS, FakeEmbedder(), cache)
    assert FakeEmbedder.calls == 2
