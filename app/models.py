from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.services.text import normalize


def page_ref(row_id: int, label: str | None) -> str:
    """The last part of a work's or composer's address, e.g. 42-sonata-para-piano-n-14."""
    slug = normalize(label).replace(" ", "-")[:80].strip("-")
    return f"{row_id}-{slug}" if slug else str(row_id)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    role: Mapped[str] = mapped_column(String, default="Visitor")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True
    )

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")
    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="user")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)

    events: Mapped[list["ExamEvent"]] = relationship("ExamEvent", back_populates="region")


class Discipline(Base):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)

    events: Mapped[list["ExamEvent"]] = relationship("ExamEvent", back_populates="discipline")


class ExamEvent(Base):
    __tablename__ = "exam_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column()
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))

    region: Mapped["Region"] = relationship("Region", back_populates="events")
    discipline: Mapped["Discipline"] = relationship("Discipline", back_populates="events")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="event")

    __table_args__ = (
        UniqueConstraint("year", "region_id", "discipline_id", name="uix_year_region_discipline"),
    )


class Composer(Base):
    __tablename__ = "composers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    # normalize(name): accent- and case-insensitive matching. Kept in sync by a listener below.
    search_text: Mapped[str | None] = mapped_column(String)
    wikidata_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    openopus_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    works: Mapped[list["Work"]] = relationship("Work", back_populates="composer")

    @property
    def url_path(self) -> str:
        """Address of the composer's page. The id decides; the slug is for readers."""
        return f"/compositores/{page_ref(self.id, self.name)}"


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    nickname: Mapped[str | None] = mapped_column(String)
    # normalize(title + nickname). Kept in sync by a listener below.
    search_text: Mapped[str | None] = mapped_column(String)
    openopus_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    composer_id: Mapped[int] = mapped_column(ForeignKey("composers.id"))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    composer: Mapped["Composer"] = relationship("Composer", back_populates="works")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="work")

    imslp_url: Mapped[str | None] = mapped_column(String)

    @property
    def url_path(self) -> str:
        """Address of the work's page. The id decides; the slug is for readers."""
        return f"/obras/{page_ref(self.id, self.title)}"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("exam_events.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"))
    movement_details: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True
    )
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="reports")
    event: Mapped["ExamEvent"] = relationship("ExamEvent", back_populates="reports")
    work: Mapped["Work"] = relationship("Work", back_populates="reports")
    votes: Mapped[list["Vote"]] = relationship(
        "Vote", back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("event_id", "work_id", name="uix_event_work_report"),)


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    # Denormalised from report.event_id so "one participation per user and event" can be
    # a database constraint instead of a check-then-insert race.
    event_id: Mapped[int] = mapped_column(ForeignKey("exam_events.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="votes")
    report: Mapped["Report"] = relationship("Report", back_populates="votes")

    __table_args__ = (Index("uix_vote_user_event", "user_id", "event_id", unique=True),)


# search_text is derived data. Setting it here, rather than at each place a Composer or
# Work is created (services, scripts, tests), means no code path can leave it stale.
@event.listens_for(Composer, "before_insert")
@event.listens_for(Composer, "before_update")
def _set_composer_search_text(_mapper: Any, _connection: Any, target: Composer) -> None:
    target.search_text = normalize(target.name)


@event.listens_for(Work, "before_insert")
@event.listens_for(Work, "before_update")
def _set_work_search_text(_mapper: Any, _connection: Any, target: Work) -> None:
    target.search_text = normalize(f"{target.title} {target.nickname or ''}")
