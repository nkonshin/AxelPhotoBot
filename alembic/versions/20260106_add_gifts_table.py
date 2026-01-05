"""Add gifts table and gift fields to payments

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create gifts table and add gift fields to payments."""
    # Add gift fields to payments table
    op.add_column('payments', sa.Column('is_gift', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('payments', sa.Column('gift_recipient_username', sa.String(255), nullable=True))
    
    # Create gifts table
    op.create_table(
        'gifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_username', sa.String(255), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('package', sa.String(50), nullable=False),
        sa.Column('tokens_amount', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_gifts_recipient_username', 'gifts', ['recipient_username'])
    op.create_index('ix_gifts_sender_id', 'gifts', ['sender_id'])


def downgrade() -> None:
    """Drop gifts table and remove gift fields from payments."""
    op.drop_index('ix_gifts_sender_id', table_name='gifts')
    op.drop_index('ix_gifts_recipient_username', table_name='gifts')
    op.drop_table('gifts')
    
    op.drop_column('payments', 'gift_recipient_username')
    op.drop_column('payments', 'is_gift')
