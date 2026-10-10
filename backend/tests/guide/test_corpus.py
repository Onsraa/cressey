import shutil
from pathlib import Path

import pytest

from cressey.guide.corpus import (
    CorpusIntegrityError,
    build_corpus,
    check_sources,
    extract_anssi,
    load_atlas,
    load_corpus,
)
from cressey.guide.quotes import normalize

REF = Path(__file__).parents[2] / "data" / "reference"


def test_anssi_fr_has_35_recommendations():
    units = extract_anssi(REF / "anssi_genai_fr.pdf", "fr")
    assert sorted(int(u.id.split(":R")[1]) for u in units) == list(range(1, 36))
    r9 = next(u for u in units if u.id == "anssi-fr:R9")
    assert normalize(r9.text).startswith("r9 proscrire l'usage automatisé")
    assert "doit être configuré de manière à ne pas être en mesure" in normalize(
        r9.text
    )


def test_anssi_en_has_35_recommendations():
    assert len(extract_anssi(REF / "anssi_genai_en.pdf", "en")) == 35


def test_atlas_includes_agent_mitigations():
    ids = {u.id for u in load_atlas(REF / "ATLAS.yaml")}
    want = {f"atlas:AML.M00{n}" for n in (26, 27, 28, 29, 30, 33)}
    assert want <= ids


def _copy_ref(tmp_path: Path) -> Path:
    dst = tmp_path / "reference"
    shutil.copytree(REF, dst)
    return dst


def test_source_hash_mismatch_is_refused(tmp_path):
    ref = _copy_ref(tmp_path)
    with (ref / "ATLAS.yaml").open("a") as f:
        f.write("#")
    with pytest.raises(CorpusIntegrityError, match="ATLAS.yaml"):
        check_sources(ref)


def test_missing_owasp_is_a_warning_not_an_error(tmp_path, caplog):
    ref = _copy_ref(tmp_path)
    (ref / "owasp_asi.json").unlink(missing_ok=True)
    units = build_corpus(ref, tmp_path / "corpus.json")
    assert not any(u.source == "owasp" for u in units)
    assert "owasp_asi.json" in caplog.text


def test_edited_corpus_json_is_refused(tmp_path):
    ref = _copy_ref(tmp_path)
    out = tmp_path / "corpus.json"
    build_corpus(ref, out)
    out.write_text(out.read_text().replace("R9", "R8", 1))
    with pytest.raises(CorpusIntegrityError):
        load_corpus(out)


def test_unpinned_runbook_is_refused(tmp_path):
    ref = _copy_ref(tmp_path)
    (ref / "runbooks" / "rotation-urgente.md").write_text("# Rotation urgente\nTexte.")
    with pytest.raises(CorpusIntegrityError, match="rotation-urgente.md"):
        check_sources(ref)


def test_app_refuses_to_start_on_an_edited_corpus(tmp_path, monkeypatch):
    import cressey.app
    from cressey.settings import Settings

    data = Path(__file__).parents[2] / "data"
    for name in ("corpus.json", "corpus.sha256"):
        shutil.copy(data / name, tmp_path / name)
    edited = tmp_path / "corpus.json"
    edited.write_text(edited.read_text().replace("R9", "R8", 1))
    monkeypatch.setattr(cressey.app, "DATA", tmp_path, raising=False)
    with pytest.raises(CorpusIntegrityError):
        cressey.app.create_app(Settings(_env_file=None))
