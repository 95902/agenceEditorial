"""Add article generation tables (generated_articles, generated_article_images, generated_article_versions).

Revision ID: f50ad65afb32
Revises: e40ad65afb31
Create Date: 2025-12-15 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f50ad65afb32"
down_revision: Union[str, None] = "e40ad65afb31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # generated_articles
    op.create_table(
        "generated_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_profile_id", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tone", sa.String(length=50), nullable=True),
        sa.Column("target_words", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="fr"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="initialized"),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("quality_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("meta_description", sa.String(length=500), nullable=True),
        sa.Column("final_word_count", sa.Integer(), nullable=True),
        sa.Column("seo_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("readability_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("output_path", sa.String(length=500), nullable=True),
        sa.Column("validated_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["site_profile_id"],
            ["site_profiles.id"],
            name="fk_generated_articles_site_profile_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_generated_articles_plan_id"),
    )
    op.create_index(
        "ix_generated_articles_plan_id",
        "generated_articles",
        ["plan_id"],
        unique=True,
    )
    op.create_index(
        "ix_generated_articles_site_profile_id",
        "generated_articles",
        ["site_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_generated_articles_status",
        "generated_articles",
        ["status"],
        unique=False,
    )

    # generated_article_images
    op.create_table(
        "generated_article_images",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("image_type", sa.String(length=50), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("local_path", sa.String(length=500), nullable=True),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["generated_articles.id"],
            name="fk_generated_article_images_article_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_article_images_article_id",
        "generated_article_images",
        ["article_id"],
        unique=False,
    )

    # generated_article_versions
    op.create_table(
        "generated_article_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_description", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["generated_articles.id"],
            name="fk_generated_article_versions_article_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "version", name="uq_article_version"),
    )
    op.create_index(
        "ix_generated_article_versions_article_id",
        "generated_article_versions",
        ["article_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generated_article_versions_article_id", table_name="generated_article_versions")
    op.drop_table("generated_article_versions")

    op.drop_index("ix_generated_article_images_article_id", table_name="generated_article_images")
    op.drop_table("generated_article_images")

    op.drop_index("ix_generated_articles_status", table_name="generated_articles")
    op.drop_index("ix_generated_articles_site_profile_id", table_name="generated_articles")
    op.drop_index("ix_generated_articles_plan_id", table_name="generated_articles")
    op.drop_table("generated_articles")





