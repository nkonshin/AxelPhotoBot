"""Increase prompt field length from 2000 to 3500 characters.

Revision ID: increase_prompt_length
Revises: add_transactions_table
Create Date: 2026-01-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'increase_prompt_length'
down_revision: Union[str, None] = 'add_transactions_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase prompt column length in generation_tasks table."""
    # Alter column type from VARCHAR(2000) to VARCHAR(3500)
    op.alter_column(
        'generation_tasks',
        'prompt',
        type_=sa.String(3500),
        existing_type=sa.String(2000),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert prompt column length back to 2000."""
    # Note: This will fail if there are prompts longer than 2000 chars
    op.alter_column(
        'generation_tasks',
        'prompt',
        type_=sa.String(2000),
        existing_type=sa.String(3500),
        existing_nullable=False,
    )
