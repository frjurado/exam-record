"""add event_id to votes, unique per user and event

Revision ID: a3f1c2d4e5b6
Revises: e07ef69ec28e
Create Date: 2026-11-11 12:00:00.000000

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c2d4e5b6"
down_revision: str | Sequence[str] | None = "e07ef69ec28e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    """Add votes.event_id (backfilled from reports) and a unique (user_id, event_id) index.

    Migrations run at container boot and a failure keeps the site down, so this must
    not fail on existing data. The column is added with a plain ALTER TABLE (no table
    rebuild), and the unique index is only created if no user already holds two votes
    in the same event. If it is skipped, resolve the duplicates by hand and create the
    index in a follow-up migration; until then the application-level check still applies.
    """
    op.execute("ALTER TABLE votes ADD COLUMN event_id INTEGER REFERENCES exam_events (id)")
    op.execute(
        "UPDATE votes SET event_id = "
        "(SELECT reports.event_id FROM reports WHERE reports.id = votes.report_id)"
    )

    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM ("
                "SELECT 1 FROM votes WHERE event_id IS NOT NULL "
                "GROUP BY user_id, event_id HAVING COUNT(*) > 1)"
            )
        )
        .scalar_one()
    )
    if duplicates:
        logger.warning(
            "SKIPPED unique index uix_vote_user_event: %d (user, event) pairs hold more "
            "than one vote. Resolve them and create the index in a follow-up migration.",
            duplicates,
        )
        return

    op.create_index("uix_vote_user_event", "votes", ["user_id", "event_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS uix_vote_user_event")
    with op.batch_alter_table("votes", schema=None) as batch_op:
        batch_op.drop_column("event_id")
