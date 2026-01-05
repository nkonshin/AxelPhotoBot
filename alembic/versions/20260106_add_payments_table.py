"""Add payments table for YooKassa integration

Revision ID: f1a2b3c4d5e6
Revises: 
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create payments table."""
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('yookassa_payment_id', sa.String(100), nullable=False),
        sa.Column('package', sa.String(50), nullable=False),
        sa.Column('tokens_amount', sa.Integer(), nullable=False),
        sa.Column('amount_value', sa.String(20), nullable=False),
        sa.Column('amount_currency', sa.String(10), nullable=False, server_default='RUB'),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('paid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirmation_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payments_yookassa_payment_id', 'payments', ['yookassa_payment_id'], unique=True)
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])


def downgrade() -> None:
    """Drop payments table."""
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_index('ix_payments_yookassa_payment_id', table_name='payments')
    op.drop_table('payments')
