import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import DATA, Settings
from cressey.testing import ADMIN_AUTH


def test_the_eval_reports_are_served_with_their_file_and_date():
    app = create_app(
        Settings(_env_file=None, openai_api_key=None, typesafe_api_key=None)
    )
    reports = {
        r["kind"]: r
        for r in TestClient(app, headers=ADMIN_AUTH).get("/api/eval").json()
    }
    guides, detection = reports["guides"], reports["detection"]
    assert guides["file"] == "data/eval/report-dev.json" and guides["split"] == "dev"
    assert detection["file"] == "data/eval/report-detection.json"
    # Served as written, whatever the last recording measured.
    for r in reports.values():
        assert r["report"] == json.loads((DATA.parent / r["file"]).read_text())
    decision = reports["decision"]
    assert decision["file"] == "data/eval/decision-model.json"
    assert "calibration" in decision["report"]["write_judgment"]
    assert all(datetime.fromisoformat(r["date"]) for r in reports.values())


def _eval_client() -> TestClient:
    app = create_app(
        Settings(_env_file=None, openai_api_key=None, typesafe_api_key=None)
    )
    return TestClient(app, headers=ADMIN_AUTH)


def test_every_served_report_carries_its_own_date():
    served = _eval_client().get("/api/eval").json()
    kinds = {r["kind"] for r in served}
    assert kinds == {"guides", "detection", "ablation", "decision"}
    for r in served:
        written = json.loads((DATA.parent / r["file"]).read_text())
        assert r["date"] == written["date"]


def test_a_report_without_a_date_fails_rather_than_getting_one(tmp_path, monkeypatch):
    folder = tmp_path / "data" / "eval"
    folder.mkdir(parents=True)
    (folder / "report-dev.json").write_text(json.dumps({"split": "dev"}))
    (folder / "decision-model.json").write_text(
        json.dumps({"date": "2026-10-10T19:51:17+00:00"})
    )
    monkeypatch.setattr("cressey.api.control.DATA", tmp_path / "data")
    with pytest.raises(KeyError, match="date"):
        _eval_client().get("/api/eval")
