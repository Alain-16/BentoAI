"""add quantity to requirements, and correct the pending_questions default

Revision ID: b7e21c05a4f1
Revises: ffa8ec06dcad
Create Date: 2026-09-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7e21c05a4f1"
down_revision: Union[str, Sequence[str], None] = "ffa8ec06dcad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # How many of each thing to buy. server_default is required because the
    # column is NOT NULL and there are already requirement rows - without it
    # the ALTER fails on every one of them.
    op.add_column(
        "mission_requirements",
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
    )

    # pending_questions holds a LIST, but its column was created with an empty
    # OBJECT as the default. Every row written before now therefore holds {}
    # where the code expects [] - and MissionWithPlan declares it as
    # list[dict], so pydantic refuses to serialise those rows and GET
    # /missions/{id} fails on any mission created before this migration.
    #
    # Two fixes: correct the existing rows, and correct the default so new ones
    # are right.
    op.execute(
        "UPDATE shopping_missions SET pending_questions = '[]'::jsonb "
        "WHERE jsonb_typeof(pending_questions) <> 'array'"
    )
    op.alter_column(
        "shopping_missions",
        "pending_questions",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "shopping_missions",
        "pending_questions",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )
    op.drop_column("mission_requirements", "quantity")
