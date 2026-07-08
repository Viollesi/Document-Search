"""create documents table

Revision ID: 202607070001
Revises:
Create Date: 2026-07-07 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607070001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rubrics", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_date", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("documents")
