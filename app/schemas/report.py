from enum import StrEnum

from pydantic import BaseModel


class ScopeEnum(StrEnum):
    WHOLE_WORK = "Whole Work"
    MOVEMENT = "Movement"
    EXCERPT = "Excerpt"


class ComposerInput(BaseModel):
    id: int | None = None
    wikidata_id: str | None = None
    name: str | None = None


class WorkInput(BaseModel):
    id: int | None = None
    openopus_id: str | None = None
    title: str | None = None
    genre: str | None = None
    key: str | None = None
    opus: str | None = None
    number: str | None = None


class ReportCreate(BaseModel):
    event_id: int
    composer: ComposerInput
    work: WorkInput
    scope: ScopeEnum
    movement_details: str | None = None
    turnstile_token: str | None = None  # Optional for backend compat, but frontend sends it


class ReportResponse(BaseModel):
    id: int
    status: str = "created"
