"""Eval harness: numbers for the fiche défense. Run: uv run python -m cressey.guide.eval --split dev"""

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from cressey.guide.models import GuideIncident
from cressey.guide.pipeline import GuidePipeline


class BM25Baseline(Protocol):
    def bm25_top(self, q: str, k: int) -> list[str]: ...


class EvalReport(BaseModel):
    split: str
    n_questions: int
    hit_at_3_bm25: float
    hit_at_3_hybrid: float
    hit_at_3_reranked: float
    n_out_of_scope: int
    unsure_correct: int
    n_incidents: int
    citation_validity: float
    unsure_rate: float
    latency_p50_ms: float
    latency_p95_ms: float


def same_unit(a: str, b: str) -> bool:
    """anssi-fr:Rn and anssi-en:Rn are the same recommendation."""
    return a.replace("anssi-en:", "anssi-fr:") == b.replace("anssi-en:", "anssi-fr:")


def _hit(expected: list[str], got: list[str]) -> bool:
    return any(same_unit(e, g) for e in expected for g in got[:3])


def evaluate(
    pipeline: GuidePipeline,
    bm25: BM25Baseline,
    retrieval_set: Path,
    incident_set: Path,
    split: str,
) -> EvalReport:
    qs = [q for q in json.loads(retrieval_set.read_text()) if q["split"] == split]
    answerable = [q for q in qs if q["expected"]]
    hits = {"bm25": 0, "hybrid": 0, "reranked": 0}
    unsure_ok = 0
    for q in qs:
        fr, en = pipeline.rewriter.rewrite_question(q["q"])
        found = pipeline.retriever.search([fr, en, q["q"]])
        kept = [u.id for u in pipeline.keep(fr, found)]
        if not q["expected"]:
            unsure_ok += not kept
            continue
        hits["bm25"] += _hit(q["expected"], bm25.bm25_top(q["q"], 8))
        hits["hybrid"] += _hit(q["expected"], [u.id for u in found])
        hits["reranked"] += _hit(q["expected"], kept)

    incs = [
        GuideIncident.model_validate(i)
        for i in json.loads(incident_set.read_text())
        if i["split"] == split
    ]
    kept_steps = total_steps = unsure = 0
    latencies: list[float] = []
    for inc in incs:
        t = time.perf_counter()
        g = pipeline.run(inc)
        latencies.append(1000 * (time.perf_counter() - t))
        kept_steps += len(g.steps)
        total_steps += len(g.steps) + g.dropped_steps
        unsure += g.status != "ok"

    n = len(answerable) or 1
    q95 = (
        statistics.quantiles(latencies, n=20)[-1]
        if len(latencies) > 1
        else (latencies or [0.0])[0]
    )
    return EvalReport(
        split=split,
        n_questions=len(answerable),
        hit_at_3_bm25=hits["bm25"] / n,
        hit_at_3_hybrid=hits["hybrid"] / n,
        hit_at_3_reranked=hits["reranked"] / n,
        n_out_of_scope=len(qs) - len(answerable),
        unsure_correct=unsure_ok,
        n_incidents=len(incs),
        citation_validity=kept_steps / total_steps if total_steps else 0.0,
        unsure_rate=unsure / len(incs) if incs else 0.0,
        latency_p50_ms=statistics.median(latencies) if latencies else 0.0,
        latency_p95_ms=q95,
    )


if __name__ == "__main__":
    from cressey.guide.api import get_pipeline
    from cressey.guide.corpus import DATA
    from cressey.guide.retrieve import Retriever

    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    split = ap.parse_args().split
    pipe = get_pipeline()
    if not isinstance(pipe.retriever, Retriever):
        raise SystemExit("eval needs the real Retriever")
    report = evaluate(
        pipe,
        pipe.retriever,
        DATA / "eval" / "retrieval.json",
        DATA / "eval" / "incidents.json",
        split,
    )
    out = DATA / "eval" / f"report-{split}.json"
    out.write_text(report.model_dump_json(indent=2))
    print(report.model_dump_json(indent=2))
