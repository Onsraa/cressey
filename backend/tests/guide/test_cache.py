import numpy as np
import pytest

from cressey.guide.cache import Cached, cache_key
from cressey.guide.clients import ModelUnavailable
from cressey.guide.models import GuideDraft
from tests.guide.test_pipeline import GOOD, INC, R9, Rer, Rew, Wri


class CountingRew(Rew):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def rewrite_incident(self, incident):
        self.calls += 1
        return super().rewrite_incident(incident)


def test_replay_hit_returns_recorded_answer(tmp_path):
    Cached(Rew(), "rewriter", "m", "v1", "record", tmp_path).rewrite_incident(INC)
    assert Cached(
        Rew(fail=True), "rewriter", "m", "v1", "replay", tmp_path
    ).rewrite_incident(INC) == ("fr", "en")


def test_replay_miss_raises_and_never_calls_inner(tmp_path):
    inner = CountingRew()
    with pytest.raises(ModelUnavailable):
        Cached(inner, "rewriter", "m", "v1", "replay", tmp_path).rewrite_incident(INC)
    assert inner.calls == 0


def test_fallback_uses_cache_only_when_live_fails(tmp_path):
    Cached(Rew(), "rewriter", "m", "v1", "record", tmp_path).rewrite_incident(INC)
    assert Cached(
        Rew(fail=True), "rewriter", "m", "v1", "fallback", tmp_path
    ).rewrite_incident(INC) == ("fr", "en")
    with pytest.raises(ModelUnavailable):
        Cached(
            Rew(fail=True), "rewriter", "m", "v1", "fallback", tmp_path / "empty"
        ).rewrite_incident(INC)


def test_prompt_version_change_misses_the_cache():
    assert cache_key("rewriter", "m", "v1", {"x": 1}) != cache_key(
        "rewriter", "m", "v2", {"x": 1}
    )


def test_round_trips_every_output_type(tmp_path):
    class Emb:
        def embed(self, texts):
            return np.array([[0.6, 0.8]])

    for mode in ("record", "replay"):
        c_emb = Cached(
            Emb() if mode == "record" else None, "embedder", "m", "v1", mode, tmp_path
        )
        assert np.allclose(c_emb.embed(["x"]), [[0.6, 0.8]])
        c_rer = Cached(
            Rer(0.7) if mode == "record" else None,
            "reranker",
            "m",
            "v1",
            mode,
            tmp_path,
        )
        assert c_rer.relevance("q", [R9]) == {R9.id: 0.7}
        c_wri = Cached(
            Wri(GuideDraft(steps=[GOOD])) if mode == "record" else None,
            "writer",
            "m",
            "v1",
            mode,
            tmp_path,
        )
        assert c_wri.write(INC, [R9]).steps[0].source_id == GOOD.source_id
        assert c_wri.answer("pourquoi ?", [R9]).steps


def test_a_new_incident_id_still_replays_the_rewrite(tmp_path):
    Cached(Rew(), "rewriter", "m", "v1", "record", tmp_path).rewrite_incident(INC)
    again = INC.model_copy(update={"id": "i-new"})
    assert Cached(
        Rew(fail=True), "rewriter", "m", "v1", "replay", tmp_path
    ).rewrite_incident(again) == ("fr", "en")


def test_a_new_incident_id_still_replays_the_guide(tmp_path):
    Cached(Wri(), "writer", "m", "v1", "record", tmp_path).write(INC, [R9])
    again = INC.model_copy(update={"id": "i-new"})
    draft = Cached(Wri(fail=True), "writer", "m", "v1", "replay", tmp_path).write(
        again, [R9]
    )
    assert draft == GuideDraft(steps=[GOOD])
