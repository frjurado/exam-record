"""add search_text to composers and works, store report details as plain text

Revision ID: b7d2e9f0a1c3
Revises: a3f1c2d4e5b6
Create Date: 2026-11-11 18:00:00.000000

"""

import logging
import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e9f0a1c3"
down_revision: str | Sequence[str] | None = "a3f1c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")


def _normalize(text: str | None) -> str:
    # Frozen copy of app.services.text.normalize as of this revision, so the migration
    # keeps producing the same values even if the application function changes later.
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    folded = re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()
    return re.sub(r"\b(?:n o|no|num|numero|n) (?=\d)", "n ", folded)


def _plain_details(details: str) -> str | None:
    """'[Movement] Mov. 2 (Allegro)' -> 'Mov. 2 (Allegro)'; drop the redundant 'Obra Completa - '."""
    text = re.sub(r"^\[(Movement|Excerpt|Whole Work)\]\s*", "", details).strip()
    text = re.sub(r"^Obra Completa - Fragmento:\s*", "Fragmento: ", text)
    text = re.sub(r"\s+- Fragmento:\s*", " · fragmento: ", text)
    text = text.strip().rstrip(":").strip()
    if not text:
        return "Movimiento" if details.startswith("[Movement]") else "Fragmento"
    return text


def _translate_catalogue_titles(bind: sa.engine.Connection) -> None:
    """Render the English titles of works that came from OpenOpus in Spanish.

    Uses the application's translator rather than a frozen copy (the glossary is large).
    It is cosmetic, so any failure is logged and skipped instead of blocking startup.
    """
    try:
        from app.services.titles import localize_openopus_title

        rows = bind.execute(
            sa.text("SELECT id, title, nickname FROM works WHERE openopus_id IS NOT NULL")
        ).all()
        for work_id, title, nickname in rows:
            new_title, found_nickname = localize_openopus_title(title)
            bind.execute(
                sa.text("UPDATE works SET title = :title, nickname = :nickname WHERE id = :id"),
                {"title": new_title, "nickname": nickname or found_nickname, "id": work_id},
            )
    except Exception:
        logger.exception("Skipped translating catalogue titles")


def upgrade() -> None:
    """Plain ALTER TABLE ADD COLUMN and row updates only: nothing here can fail on existing data."""
    op.execute("ALTER TABLE composers ADD COLUMN search_text VARCHAR")
    op.execute("ALTER TABLE works ADD COLUMN search_text VARCHAR")

    bind = op.get_bind()
    _translate_catalogue_titles(bind)
    for composer_id, name in bind.execute(sa.text("SELECT id, name FROM composers")).all():
        bind.execute(
            sa.text("UPDATE composers SET search_text = :value WHERE id = :id"),
            {"value": _normalize(name), "id": composer_id},
        )
    for work_id, title, nickname in bind.execute(
        sa.text("SELECT id, title, nickname FROM works")
    ).all():
        bind.execute(
            sa.text("UPDATE works SET search_text = :value WHERE id = :id"),
            {"value": _normalize(f"{title} {nickname or ''}"), "id": work_id},
        )

    rows = bind.execute(
        sa.text("SELECT id, movement_details FROM reports WHERE movement_details LIKE '[%'")
    ).all()
    for report_id, details in rows:
        bind.execute(
            sa.text("UPDATE reports SET movement_details = :value WHERE id = :id"),
            {"value": _plain_details(details), "id": report_id},
        )


def downgrade() -> None:
    """Drop the search columns. The reworded report details are not restored."""
    with op.batch_alter_table("works", schema=None) as batch_op:
        batch_op.drop_column("search_text")
    with op.batch_alter_table("composers", schema=None) as batch_op:
        batch_op.drop_column("search_text")
