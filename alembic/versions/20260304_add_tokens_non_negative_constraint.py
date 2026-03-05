"""Add CHECK constraint to prevent negative token balance.

Revision ID: add_tokens_non_negative
Revises: increase_prompt_length
Create Date: 2026-03-04
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_tokens_non_negative'
down_revision: Union[str, None] = 'increase_prompt_length'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraint ensuring tokens >= 0."""
    # Fix any existing negative balances before adding constraint
    op.execute("UPDATE users SET tokens = 0 WHERE tokens < 0")
    op.create_check_constraint(
        "ck_users_tokens_non_negative",
        "users",
        "tokens >= 0",
    )


def downgrade() -> None:
    """Remove the non-negative tokens constraint."""
    op.drop_constraint("ck_users_tokens_non_negative", "users", type_="check")
