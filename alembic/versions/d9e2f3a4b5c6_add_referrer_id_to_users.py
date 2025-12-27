"""Add referrer_id to users

Revision ID: d9e2f3a4b5c6
Revises: c8f1a2d3e4f5
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e2f3a4b5c6'
down_revision: Union[str, None] = 'c8f1a2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add referrer_id column to users table
    op.add_column(
        'users',
        sa.Column('referrer_id', sa.Integer(), nullable=True)
    )
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_users_referrer_id',
        'users',
        'users',
        ['referrer_id'],
        ['id']
    )
    # Add index for faster referral lookups
    op.create_index('ix_users_referrer_id', 'users', ['referrer_id'])


def downgrade() -> None:
    op.drop_index('ix_users_referrer_id', table_name='users')
    op.drop_constraint('fk_users_referrer_id', 'users', type_='foreignkey')
    op.drop_column('users', 'referrer_id')
