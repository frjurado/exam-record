from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="Visitor", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reports = relationship("Report", back_populates="user")

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)

    events = relationship("ExamEvent", back_populates="region")

class Discipline(Base):
    __tablename__ = "disciplines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)

    events = relationship("ExamEvent", back_populates="discipline")

class ExamEvent(Base):
    __tablename__ = "exam_events"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)

    region = relationship("Region", back_populates="events")
    discipline = relationship("Discipline", back_populates="events")
    reports = relationship("Report", back_populates="event")

    __table_args__ = (
        UniqueConstraint('year', 'region_id', 'discipline_id', name='uix_year_region_discipline'),
    )

class Composer(Base):
    __tablename__ = "composers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True, nullable=True)
    openopus_id = Column(String, unique=True, index=True, nullable=True)
    is_verified = Column(Boolean, default=False)

    works = relationship("Work", back_populates="composer")

class Work(Base):
    __tablename__ = "works"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    nickname = Column(String, nullable=True)
    openopus_id = Column(String, unique=True, index=True, nullable=True)
    composer_id = Column(Integer, ForeignKey("composers.id"), nullable=False)
    is_verified = Column(Boolean, default=False)

    composer = relationship("Composer", back_populates="works")
    reports = relationship("Report", back_populates="work")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("exam_events.id"), nullable=False)
    work_id = Column(Integer, ForeignKey("works.id"), nullable=False)
    movement_details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_flagged = Column(Boolean, default=False)

    user = relationship("User", back_populates="reports")
    event = relationship("ExamEvent", back_populates="reports")
    work = relationship("Work", back_populates="reports")
    votes = relationship("Vote", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('event_id', 'work_id', name='uix_event_work_report'),
    )

class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    report = relationship("Report", back_populates="votes")
