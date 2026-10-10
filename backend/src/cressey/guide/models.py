from typing import Literal

from pydantic import BaseModel

Leg = Literal["pressure", "opportunity", "rationalization"]
OwnerRole = Literal["key_owner", "task_author", "platform_owner", "soc"]
Status = Literal["ok", "unsure", "unavailable"]


class Unit(BaseModel):
    id: str  # anssi-fr:R9, atlas:AML.M0029, owasp:ASI03, runbook:rotation-des-cles
    source: Literal["anssi", "atlas", "owasp", "runbook"]
    lang: Literal["fr", "en"]
    title: str
    text: str


class GuideIncident(BaseModel):
    id: str
    leg: Leg
    owner_role: OwnerRole
    summary: str
    source: str


class DraftStep(BaseModel):
    action: str
    source_id: str
    quote: str


class GuideDraft(BaseModel):
    steps: list[DraftStep]


class GuideStep(BaseModel):
    action: str
    source_id: str
    quote: str
    source_title: str


class Guide(BaseModel):
    id: str
    incident_id: str
    status: Status
    message: str | None
    steps: list[GuideStep]
    passages: list[Unit]
    dropped_steps: int


class WhyAnswer(BaseModel):
    text: str
    citations: list[GuideStep]
    status: Status
