"""Extend source_image_url to 2000 characters

Revision ID: extend_source_url
Revises: e1f2a3b4c5d6
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'extend_source_url'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend source_image_url from 500 to 2000 characters."""
    op.alter_column(
        'generation_tasks',
        'source_image_url',
        existing_type=sa.String(500),
        type_=sa.String(2000),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert source_image_url back to 500 characters."""
    op.alter_column(
        'generation_tasks',
        'source_image_url',
        existing_type=sa.String(2000),
        type_=sa.String(500),
        existing_nullable=True,
    )
