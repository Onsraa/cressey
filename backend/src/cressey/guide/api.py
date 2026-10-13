from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from cressey.domain.guides import Guide, GuideIncident, WhyAnswer
from cressey.guide.cache import wrap_all
from cressey.guide.corpus import load_corpus
from cressey.guide.pipeline import GuidePipeline
from cressey.guide.retrieve import Retriever
from cressey.guide.store import GuideStore
from cressey.settings import DATA, Settings

router = APIRouter(prefix="/guides", tags=["guides"])


@cache
def get_pipeline() -> GuidePipeline:
    s = Settings()
    embedder, rewriter, reranker, writer = wrap_all(s)
    retriever = Retriever(
        load_corpus(DATA / "corpus.json"), embedder, DATA / "embeddings.npy"
    )
    return GuidePipeline(retriever, rewriter, reranker, writer, s.relevance_min)


@cache
def get_store() -> GuideStore:
    return GuideStore(DATA / "guides.sqlite")


def write_guide(incident: GuideIncident) -> Guide:
    """Write and store the guide for an incident the core loop opened."""
    guide = get_pipeline().run(incident)
    get_store().put(guide)
    return guide


PipelineDep = Annotated[GuidePipeline, Depends(get_pipeline)]
StoreDep = Annotated[GuideStore, Depends(get_store)]


class WhyRequest(BaseModel):
    question: str = Field(max_length=500)

    @field_validator("question")
    @classmethod
    def _min_three_chars(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("question must have at least 3 characters")
        return v.strip()


@router.post("", status_code=201)
def create_guide(
    incident: GuideIncident,
    pipeline: PipelineDep,
    store: StoreDep,
) -> Guide:
    guide = pipeline.run(incident)
    store.put(guide)
    return guide


@router.get("/{gid}")
def read_guide(gid: str, store: StoreDep) -> Guide:
    guide = store.get(gid)
    if guide is None:
        raise HTTPException(404, "guide not found")
    return guide


@router.post("/{gid}/why")
def why(
    gid: str,
    body: WhyRequest,
    pipeline: PipelineDep,
    store: StoreDep,
) -> WhyAnswer:
    guide = store.get(gid)
    if guide is None:
        raise HTTPException(404, "guide not found")
    return pipeline.why(guide, body.question)
