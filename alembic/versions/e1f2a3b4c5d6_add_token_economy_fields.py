"""Add token economy fields

Revision ID: e1f2a3b4c5d6
Revises: d9e2f3a4b5c6
Create Date: 2026-01-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd9e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add api_tokens_spent to users table
    op.add_column('users', sa.Column('api_tokens_spent', sa.Integer(), nullable=False, server_default='0'))
    
    # Add api_tokens_spent and images_count to generation_tasks table
    op.add_column('generation_tasks', sa.Column('api_tokens_spent', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('generation_tasks', sa.Column('images_count', sa.Integer(), nullable=False, server_default='1'))
    
    # Reset all users to 7 tokens (new token economy)
    op.execute("UPDATE users SET tokens = 7")
    
    # Update default model to gpt-image-1.5
    op.execute("UPDATE users SET selected_model = 'gpt-image-1.5' WHERE selected_model = 'gpt-image-1'")


def downgrade() -> None:
    # Remove columns
    op.drop_column('generation_tasks', 'images_count')
    op.drop_column('generation_tasks', 'api_tokens_spent')
    op.drop_column('users', 'api_tokens_spent')
