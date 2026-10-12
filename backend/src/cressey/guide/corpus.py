"""Pinned corpus: ANSSI R1–R35 (FR+EN), MITRE ATLAS mitigations, OWASP ASI (optional), runbooks."""

import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Literal

import yaml
from pypdf import PdfReader

from cressey.domain.guides import Unit
from cressey.settings import DATA

log = logging.getLogger(__name__)


class CorpusIntegrityError(Exception):
    pass


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_sources(ref: Path) -> None:
    pinned: dict[str, str] = json.loads((ref / "SOURCES.json").read_text())
    for name, digest in pinned.items():
        f = ref / name
        if not f.is_file():
            raise CorpusIntegrityError(f"missing pinned source: {name}")
        if _sha256(f) != digest:
            raise CorpusIntegrityError(f"hash mismatch: {name}")
    loaded = [ref / "owasp_asi.json", *sorted((ref / "runbooks").glob("*.md"))]
    for f in loaded:
        name = f.relative_to(ref).as_posix()
        if f.exists() and name not in pinned:
            raise CorpusIntegrityError(
                f"{name} is present but not pinned in SOURCES.json"
            )


def extract_anssi(pdf: Path, lang: Literal["fr", "en"]) -> list[Unit]:
    text = " ".join(
        " ".join((p.extract_text() or "").split()) for p in PdfReader(pdf).pages
    )
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)  # undo line-break hyphenation
    starts: dict[int, int] = {}
    for m in re.finditer(r"\bR(\d{1,2}) (?=[A-ZÉ])", text):
        n = int(m.group(1))
        if (
            1 <= n <= 35 and n not in starts
        ):  # first occurrence is the body, not the closing list
            starts[n] = m.start()
    order = sorted(starts.items(), key=lambda kv: kv[1])
    units = []
    for i, (n, s) in enumerate(order):
        end = order[i + 1][1] if i + 1 < len(order) else s + 1500
        body = text[s:end].strip()
        units.append(
            Unit(
                id=f"anssi-{lang}:R{n}",
                source="anssi",
                lang=lang,
                title=body[:120],
                text=body,
            )
        )
    return units


def load_atlas(path: Path) -> list[Unit]:
    data = yaml.safe_load(path.read_text())
    ms = [
        x for m in data.get("matrices", []) for x in m.get("mitigations", [])
    ] or data.get("mitigations", [])
    return [
        Unit(
            id=f"atlas:{x['id']}",
            source="atlas",
            lang="en",
            title=x["name"],
            text=f"{x['name']}. {' '.join(str(x.get('description', '')).split())}",
        )
        for x in ms
    ]


def load_owasp(path: Path) -> list[Unit]:
    return [
        Unit(
            id=f"owasp:{x['id']}",
            source="owasp",
            lang="en",
            title=x["title"],
            text=f"{x['title']}. {x['mitigations']}",
        )
        for x in json.loads(path.read_text())
    ]


def load_runbooks(folder: Path) -> list[Unit]:
    units = []
    for p in sorted(folder.glob("*.md")):
        t = p.read_text()
        units.append(
            Unit(
                id=f"runbook:{p.stem}",
                source="runbook",
                lang="en",
                title=t.splitlines()[0].lstrip("# ").strip(),
                text=" ".join(t.split()),
            )
        )
    return units


def build_corpus(ref: Path, out: Path) -> list[Unit]:
    check_sources(ref)
    units = extract_anssi(ref / "anssi_genai_fr.pdf", "fr") + extract_anssi(
        ref / "anssi_genai_en.pdf", "en"
    )
    units += load_atlas(ref / "ATLAS.yaml")
    if (ref / "owasp_asi.json").exists():
        units += load_owasp(ref / "owasp_asi.json")
    else:
        log.warning("owasp_asi.json not found: corpus built without OWASP")
    units += load_runbooks(ref / "runbooks")
    out.write_text(
        json.dumps([u.model_dump() for u in units], ensure_ascii=False, indent=1)
    )
    out.with_suffix(".sha256").write_text(_sha256(out))
    return units


def load_corpus(path: Path) -> list[Unit]:
    if _sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise CorpusIntegrityError(
            f"{path.name} does not match {path.with_suffix('.sha256').name}"
        )
    return [Unit.model_validate(u) for u in json.loads(path.read_text())]


if __name__ == "__main__" and sys.argv[1:] == ["build"]:
    logging.basicConfig(level=logging.INFO)
    built = build_corpus(DATA / "reference", DATA / "corpus.json")
    counts: dict[str, int] = {}
    for u in built:
        key = u.id.split(":")[0]
        counts[key] = counts.get(key, 0) + 1
    print(counts)
