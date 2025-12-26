"""Add image params (quality/size) and result file_id.

Revision ID: c8f1a2d3e4f5
Revises: 5c30b186d394
Create Date: 2025-12-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f1a2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "5c30b186d394"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "users",
        sa.Column(
            "image_quality",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "image_size",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'1024x1024'"),
        ),
    )

    op.add_column(
        "generation_tasks",
        sa.Column(
            "model",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'gpt-image-1'"),
        ),
    )
    op.add_column(
        "generation_tasks",
        sa.Column(
            "image_quality",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
    )
    op.add_column(
        "generation_tasks",
        sa.Column(
            "image_size",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'1024x1024'"),
        ),
    )
    op.add_column(
        "generation_tasks",
        sa.Column("result_file_id", sa.String(length=255), nullable=True),
    )

    # Backward compatible migration path:
    # Historically, the bot used a flat cost of 1 token per generation.
    # The new system uses OpenAI image tokens. Default settings are:
    # quality=medium, size=1024x1024 -> 1056 tokens.
    # We scale existing balances and recorded task costs to preserve
    # roughly the same number of default generations for existing users.
    op.execute(
        sa.text(
            "UPDATE users SET tokens = tokens * 1056 WHERE tokens > 0"
        )
    )
    op.execute(
        sa.text(
            "UPDATE generation_tasks SET tokens_spent = tokens_spent * 1056 WHERE tokens_spent > 0"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""

    # We do not attempt to reverse the token scaling automatically.

    op.drop_column("generation_tasks", "result_file_id")
    op.drop_column("generation_tasks", "image_size")
    op.drop_column("generation_tasks", "image_quality")
    op.drop_column("generation_tasks", "model")

    op.drop_column("users", "image_size")
    op.drop_column("users", "image_quality")
