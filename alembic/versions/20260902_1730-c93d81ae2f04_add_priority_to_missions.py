"""add priority to missions

Revision ID: c93d81ae2f04
Revises: b7e21c05a4f1
Create Date: 2026-09-02 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c93d81ae2f04"
down_revision: Union[str, Sequence[str], None] = "b7e21c05a4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The enum is stored as text with a check constraint rather than a native
# Postgres enum type - that is what _enum(native_enum=False) does throughout
# this schema, and it makes adding a value later an ordinary migration instead
# of an ALTER TYPE.
_PRIORITY = sa.Enum(
    "quality", "value", "balanced", "speed",
    name="missionpriority", native_enum=False, length=32,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "shopping_missions",
        sa.Column(
            "priority",
            _PRIORITY,
            server_default="balanced",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("shopping_missions", "priority")
