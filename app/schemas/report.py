from typing import Optional
from pydantic import BaseModel
from enum import Enum

class ScopeEnum(str, Enum):
    WHOLE_WORK = "Whole Work"
    MOVEMENT = "Movement"
    EXCERPT = "Excerpt"

class ComposerInput(BaseModel):
    id: Optional[int] = None
    wikidata_id: Optional[str] = None
    name: Optional[str] = None

class WorkInput(BaseModel):
    id: Optional[int] = None
    openopus_id: Optional[str] = None
    title: Optional[str] = None
    genre: Optional[str] = None
    key: Optional[str] = None
    opus: Optional[str] = None
    number: Optional[str] = None

class ReportCreate(BaseModel):
    event_id: int
    composer: ComposerInput
    work: WorkInput
    scope: ScopeEnum
    movement_details: Optional[str] = None
    turnstile_token: Optional[str] = None # Optional for backend compat, but frontend sends it

class ReportResponse(BaseModel):
    id: int
    status: str = "created"
