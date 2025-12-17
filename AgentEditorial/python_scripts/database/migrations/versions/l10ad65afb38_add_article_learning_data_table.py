"""Add article_learning_data table for learning system.

Revision ID: l10ad65afb38
Revises: k00ad65afb37
Create Date: 2025-01-25 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "l10ad65afb38"
down_revision: Union[str, None] = "k00ad65afb37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================================================
    # TABLE: article_learning_data
    # Table pour stocker les données d'apprentissage pour améliorer la génération d'articles
    # ===========================================================================
    op.create_table(
        "article_learning_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "article_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "site_profile_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "generation_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("prompt_used", sa.Text(), nullable=False),
        sa.Column(
            "quality_scores",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "feedback_type",
            sa.String(length=20),
            nullable=False,
            server_default="automatic",
        ),
        sa.Column(
            "is_positive",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "learned_patterns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["generated_articles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_profile_id"],
            ["site_profiles.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_article_learning_data_article_id",
        "article_learning_data",
        ["article_id"],
        unique=False,
    )
    op.create_index(
        "ix_article_learning_data_site_profile_id",
        "article_learning_data",
        ["site_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_article_learning_data_site_profile_id",
        table_name="article_learning_data",
    )
    op.drop_index(
        "ix_article_learning_data_article_id",
        table_name="article_learning_data",
    )
    op.drop_table("article_learning_data")

