from enum import StrEnum

from pydantic import BaseModel, Field


class ScopeEnum(StrEnum):
    WHOLE_WORK = "Whole Work"
    MOVEMENT = "Movement"
    EXCERPT = "Excerpt"


class ComposerInput(BaseModel):
    id: int | None = Field(None, description="Local database ID of an existing composer")
    wikidata_id: str | None = Field(
        None, description="Wikidata entity ID (e.g. Q1339 for J.S. Bach)", examples=["Q1339"]
    )
    name: str | None = Field(
        None, description="Full name of the composer", examples=["Johann Sebastian Bach"]
    )


class WorkInput(BaseModel):
    id: int | None = Field(None, description="Local database ID of an existing work")
    openopus_id: str | None = Field(
        None, description="OpenOpus work ID for verified catalogue entries", examples=["2"]
    )
    title: str | None = Field(
        None, description="Title of the work", examples=["Well-Tempered Clavier"]
    )
    genre: str | None = Field(None, description="Musical genre", examples=["Keyboard"])
    key: str | None = Field(None, description="Musical key", examples=["C major"])
    opus: str | None = Field(None, description="Opus number", examples=["BWV 846"])
    number: str | None = Field(None, description="Movement or piece number", examples=["1"])


class ReportCreate(BaseModel):
    event_id: int = Field(
        ..., description="ID of the exam event this report belongs to", examples=[42]
    )
    composer: ComposerInput = Field(
        ...,
        description="Composer identification — supply id or wikidata_id for known composers, or name to create a new entry",
    )
    work: WorkInput = Field(
        ...,
        description="Work identification — supply id or openopus_id for known works, or title/metadata to create a new entry",
    )
    scope: ScopeEnum = Field(
        ..., description="How much of the work was performed", examples=["Whole Work"]
    )
    movement_details: str | None = Field(
        None,
        description="Free-text description of which movement or excerpt was performed",
        examples=["Prelude No. 1 in C major"],
    )
    turnstile_token: str | None = Field(
        None, description="Cloudflare Turnstile CAPTCHA token from the submission form"
    )


class ReportResponse(BaseModel):
    id: int = Field(..., description="ID of the newly created report", examples=[101])
    status: str = Field(
        "created", description="Result status of the submission", examples=["created"]
    )
