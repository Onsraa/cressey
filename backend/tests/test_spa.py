from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import Settings


def _web(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text('<div id="root"></div>')
    (web / "assets" / "a.js").write_text("js")
    (tmp_path / "secret.txt").write_text("nope")
    return TestClient(create_app(Settings(_env_file=None, web_dir=web)))


def test_spa_deep_link_returns_index(tmp_path):
    r = _web(tmp_path).get("/guides/abc")
    assert r.status_code == 200 and 'id="root"' in r.text


def test_assets_are_served(tmp_path):
    assert _web(tmp_path).get("/assets/a.js").text == "js"


def test_fallback_never_serves_files_outside_web_dir(tmp_path):
    c = _web(tmp_path)
    for p in [
        "/../secret.txt",
        "/..%2Fsecret.txt",
        "/%2e%2e/secret.txt",
        "/assets/../../secret.txt",
    ]:
        assert "nope" not in c.get(p).text, p


def test_unknown_api_route_stays_404_with_web(tmp_path):
    assert _web(tmp_path).get("/api/nope").status_code == 404


def test_bare_api_path_is_404_not_index(tmp_path):
    assert _web(tmp_path).get("/api").status_code == 404
