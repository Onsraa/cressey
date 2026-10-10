from datetime import datetime

from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import Settings


def test_the_eval_reports_are_served_with_their_file_and_date():
    app = create_app(
        Settings(_env_file=None, openai_api_key=None, typesafe_api_key=None)
    )
    reports = {r["kind"]: r for r in TestClient(app).get("/api/eval").json()}
    guides, detection = reports["guides"], reports["detection"]
    assert guides["file"] == "data/eval/report-dev.json" and guides["split"] == "dev"
    assert detection["file"] == "data/eval/report-detection.json"
    assert detection["report"]["misses"] == []
    assert all(datetime.fromisoformat(r["date"]) for r in reports.values())
