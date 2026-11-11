from enum import StrEnum

from pydantic import BaseModel, Field

# Generous bounds on free text: long enough for any real name or title, short enough
# that the form cannot be used to store arbitrary content.
NAME_MAX_LENGTH = 200
DETAILS_MAX_LENGTH = 300


class ScopeEnum(StrEnum):
    WHOLE_WORK = "Whole Work"
    MOVEMENT = "Movement"
    EXCERPT = "Excerpt"


class ComposerInput(BaseModel):
    id: int | None = Field(None, description="Local database ID of an existing composer")
    openopus_id: str | None = Field(
        None, description="OpenOpus composer ID", examples=["145"], max_length=32
    )
    wikidata_id: str | None = Field(
        None,
        description="Wikidata entity ID (e.g. Q1339 for J.S. Bach)",
        examples=["Q1339"],
        pattern=r"^Q\d+$",
    )
    name: str | None = Field(
        None,
        description="Full name of the composer",
        examples=["Johann Sebastian Bach"],
        max_length=NAME_MAX_LENGTH,
    )


class WorkInput(BaseModel):
    id: int | None = Field(None, description="Local database ID of an existing work")
    openopus_id: str | None = Field(
        None,
        description="OpenOpus work ID for verified catalogue entries",
        examples=["2"],
        max_length=32,
    )
    title: str | None = Field(
        None,
        description="Title of the work",
        examples=["Sonata para piano n.º 14 en do sostenido menor, op. 27 n.º 2"],
        max_length=NAME_MAX_LENGTH,
    )
    nickname: str | None = Field(
        None,
        description="Popular name of the work",
        examples=["Claro de luna"],
        max_length=NAME_MAX_LENGTH,
    )


class ReportCreate(BaseModel):
    region_slug: str = Field(..., description="Slug of the exam's region", examples=["andalucia"])
    discipline_slug: str = Field(
        ..., description="Slug of the exam's discipline", examples=["piano"]
    )
    year: int = Field(..., description="Natural year the exam took place", examples=[2025])
    composer: ComposerInput = Field(
        ...,
        description=(
            "Composer identification — supply id, openopus_id or wikidata_id for known "
            "composers, or name to match or create an entry"
        ),
    )
    work: WorkInput = Field(
        ...,
        description=(
            "Work identification — supply id or openopus_id for known works, or title to "
            "match or create an entry"
        ),
    )
    scope: ScopeEnum = Field(
        ..., description="How much of the work was set in the exam", examples=["Whole Work"]
    )
    movement_details: str | None = Field(
        None,
        description="Which movement or excerpt was set, as text shown to other users",
        examples=["Mov. 1 (Allegro)"],
        max_length=DETAILS_MAX_LENGTH,
    )
    turnstile_token: str | None = Field(
        None, description="Cloudflare Turnstile CAPTCHA token from the submission form"
    )


class ReportResponse(BaseModel):
    id: int = Field(..., description="ID of the report the vote was added to", examples=[101])
    status: str = Field(
        "created", description="Result status of the submission", examples=["created"]
    )
