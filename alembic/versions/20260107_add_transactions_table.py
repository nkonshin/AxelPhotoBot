"""Add transactions table for tracking token movements.

Revision ID: add_transactions_table
Revises: g1h2i3j4k5l6
Create Date: 2026-01-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_transactions_table'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('tokens_amount', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('gift_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('related_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['gift_id'], ['gifts.id']),
        sa.ForeignKeyConstraint(['task_id'], ['generation_tasks.id']),
        sa.ForeignKeyConstraint(['related_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_transactions_user_id', table_name='transactions')
    op.drop_table('transactions')
