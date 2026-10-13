import pytest
from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.domain.guides import Guide, GuideDraft, WhyAnswer
from cressey.guide.api import get_pipeline, get_store
from cressey.guide.pipeline import GuidePipeline
from cressey.guide.store import GuideStore
from cressey.settings import Settings
from cressey.testing import ADMIN_AUTH
from tests.guide.test_pipeline import GOOD, R9, Rer, Retr, Rew, Wri

INC = {
    "id": "i1",
    "leg": "opportunity",
    "owner_role": "key_owner",
    "summary": "clé lue",
    "source": ".env.prod",
}


def client(tmp_path, writer=None) -> TestClient:
    app = create_app(Settings(_env_file=None))
    pipe = GuidePipeline(
        Retr([R9]), Rew(), Rer(), writer or Wri(GuideDraft(steps=[GOOD]))
    )
    store = GuideStore(tmp_path / "g.sqlite")
    app.dependency_overrides[get_pipeline] = lambda: pipe
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app, headers=ADMIN_AUTH)


def test_post_guide_then_get_it(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/guides", json=INC)
    assert r.status_code == 201 and r.json()["status"] == "ok"
    got = c.get(f"/api/guides/{r.json()['id']}")
    assert (
        got.status_code == 200
        and Guide.model_validate(got.json()).steps[0].source_id == "anssi-fr:R9"
    )


def test_unknown_guide_is_404(tmp_path):
    assert client(tmp_path).get("/api/guides/nope").status_code == 404


@pytest.mark.parametrize("q", ["", "  ", "ab"])
def test_why_rejects_empty_or_tiny_question(tmp_path, q):
    c = client(tmp_path)
    gid = c.post("/api/guides", json=INC).json()["id"]
    assert c.post(f"/api/guides/{gid}/why", json={"question": q}).status_code == 422


def test_why_answers_from_the_guide(tmp_path):
    c = client(tmp_path)
    gid = c.post("/api/guides", json=INC).json()["id"]
    a = WhyAnswer.model_validate(
        c.post(
            f"/api/guides/{gid}/why", json={"question": "Pourquoi ?? vraiment"}
        ).json()
    )
    assert a.status == "ok" and a.citations


def test_why_on_unknown_guide_is_404(tmp_path):
    assert (
        client(tmp_path)
        .post("/api/guides/nope/why", json={"question": "Pourquoi ?"})
        .status_code
        == 404
    )


def test_model_outage_is_201_unavailable_not_500(tmp_path):
    r = client(tmp_path, writer=Wri(fail=True)).post("/api/guides", json=INC)
    assert r.status_code == 201 and r.json()["status"] == "unavailable"


def test_store_survives_reopen(tmp_path):
    c = client(tmp_path)
    gid = c.post("/api/guides", json=INC).json()["id"]
    assert GuideStore(tmp_path / "g.sqlite").get(gid) is not None
