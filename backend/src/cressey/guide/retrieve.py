import hashlib
import json
import logging
from pathlib import Path

import bm25s
import numpy as np

from cressey.guide.clients import Embedder, ModelUnavailable
from cressey.guide.models import Unit

log = logging.getLogger(__name__)


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, uid in enumerate(ranking, start=1):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda uid: -scores[uid])


def _tok(texts: list[str]):
    return bm25s.tokenize(texts, stopwords=[], show_progress=False)


class Retriever:
    def __init__(self, units: list[Unit], embedder: Embedder | None, cache: Path):
        self.units = units
        self.by_id = {u.id: u for u in units}
        self.ids = [u.id for u in units]
        self.embedder = embedder
        self.bm25_only = embedder is None
        self.bm25 = bm25s.BM25()
        self.bm25.index(_tok([u.text for u in units]), show_progress=False)
        self.vectors = None if self.bm25_only else self._load_or_embed(cache)

    def _load_or_embed(self, cache: Path) -> np.ndarray | None:
        assert self.embedder is not None
        digest = hashlib.sha256(
            "".join(u.id + u.text for u in self.units).encode()
        ).hexdigest()
        meta = {"corpus_sha256": digest, "model": self.embedder.model}
        meta_path = cache.with_suffix(".meta.json")
        if cache.exists() and meta_path.exists():
            stored = json.loads(meta_path.read_text())
            vectors = np.load(cache)
            if all(stored.get(k) == v for k, v in meta.items()) and len(vectors) == len(
                self.units
            ):
                return vectors
        try:
            vectors = self.embedder.embed([u.text[:6000] for u in self.units])
        except ModelUnavailable as e:
            # Said, not silent: offline with vectors of another model, every guide's passages
            # change, so every recorded guide misses.
            log.warning(
                "corpus embeddings for %s unavailable (%s): retrieval falls back to BM25",
                self.embedder.model,
                e,
            )
            self.bm25_only = True
            return None
        np.save(cache, vectors)
        meta_path.write_text(json.dumps({**meta, "dim": int(vectors.shape[1])}))
        return vectors

    def bm25_top(self, q: str, k: int) -> list[str]:
        res, scores = self.bm25.retrieve(
            _tok([q]), k=min(k, len(self.ids)), show_progress=False
        )
        return [self.ids[j] for j, s in zip(res[0], scores[0], strict=True) if s > 0]

    def _emb_top(self, q: str, k: int) -> list[str]:
        assert self.embedder is not None and self.vectors is not None
        v = self.embedder.embed([q], query=True)[0]
        return [self.ids[j] for j in np.argsort(-(self.vectors @ v))[:k]]

    def search(self, queries: list[str], k: int = 8, top: int = 8) -> list[Unit]:
        queries = [q for q in queries if q.strip()]
        lists: list[list[str]] = []
        use_embeddings = not self.bm25_only
        for q in queries:
            lists.append(self.bm25_top(q, k))
            if use_embeddings:
                try:
                    lists.append(self._emb_top(q, k))
                except ModelUnavailable as e:
                    # BM25 only for the rest of this search; the next search tries again.
                    use_embeddings = False
                    log.warning(
                        "query embedding failed (%s): BM25 only", type(e).__name__
                    )
        return [self.by_id[uid] for uid in rrf_fuse(lists)[:top]]
