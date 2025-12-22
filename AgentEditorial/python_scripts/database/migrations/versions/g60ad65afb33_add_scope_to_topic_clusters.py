"""Add scope column to topic_clusters for topic classification.

Revision ID: g60ad65afb33
Revises: f50ad65afb32
Create Date: 2025-12-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g60ad65afb33"
down_revision: Union[str, None] = "f50ad65afb32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scope column to topic_clusters."""
    op.add_column(
        "topic_clusters",
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default="off_scope",
        ),
    )
    # Optional index to speed up filtering by analysis and scope
    op.create_index(
        "ix_topic_clusters_analysis_scope",
        "topic_clusters",
        ["analysis_id", "scope"],
        unique=False,
    )


def downgrade() -> None:
    """Remove scope column from topic_clusters."""
    op.drop_index("ix_topic_clusters_analysis_scope", table_name="topic_clusters")
    op.drop_column("topic_clusters", "scope")







