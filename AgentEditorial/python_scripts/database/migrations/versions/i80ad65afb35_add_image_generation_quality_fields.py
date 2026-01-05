"""Add image generation quality fields to generated_article_images.

Revision ID: i80ad65afb35
Revises: h70ad65afb34
Create Date: 2025-12-16 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "i80ad65afb35"
down_revision: Union[str, None] = "h70ad65afb34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quality and metadata fields to generated_article_images."""
    
    # Ajouter negative_prompt
    op.add_column(
        "generated_article_images",
        sa.Column("negative_prompt", sa.Text(), nullable=True),
    )
    
    # Ajouter generation_params (JSONB)
    op.add_column(
        "generated_article_images",
        sa.Column(
            "generation_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    
    # Ajouter quality_score (Float)
    op.add_column(
        "generated_article_images",
        sa.Column("quality_score", sa.Float(), nullable=True),
    )
    
    # Ajouter critique_details (JSONB)
    op.add_column(
        "generated_article_images",
        sa.Column(
            "critique_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    
    # Ajouter retry_count (Integer avec valeur par défaut)
    op.add_column(
        "generated_article_images",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    
    # Ajouter final_status (String(20))
    op.add_column(
        "generated_article_images",
        sa.Column("final_status", sa.String(length=20), nullable=True),
    )
    
    # Ajouter generation_time_seconds (Float)
    op.add_column(
        "generated_article_images",
        sa.Column("generation_time_seconds", sa.Float(), nullable=True),
    )
    
    # Ajouter site_profile_id (Integer, ForeignKey, nullable, avec index)
    op.add_column(
        "generated_article_images",
        sa.Column("site_profile_id", sa.Integer(), nullable=True),
    )
    
    # Ajouter la contrainte de clé étrangère
    op.create_foreign_key(
        "fk_generated_article_images_site_profile_id",
        "generated_article_images",
        "site_profiles",
        ["site_profile_id"],
        ["id"],
    )
    
    # Créer l'index sur site_profile_id
    op.create_index(
        "ix_generated_article_images_site_profile_id",
        "generated_article_images",
        ["site_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove quality and metadata fields from generated_article_images."""
    
    # Supprimer l'index
    op.drop_index(
        "ix_generated_article_images_site_profile_id",
        table_name="generated_article_images",
    )
    
    # Supprimer la contrainte de clé étrangère
    op.drop_constraint(
        "fk_generated_article_images_site_profile_id",
        "generated_article_images",
        type_="foreignkey",
    )
    
    # Supprimer les colonnes
    op.drop_column("generated_article_images", "site_profile_id")
    op.drop_column("generated_article_images", "generation_time_seconds")
    op.drop_column("generated_article_images", "final_status")
    op.drop_column("generated_article_images", "retry_count")
    op.drop_column("generated_article_images", "critique_details")
    op.drop_column("generated_article_images", "quality_score")
    op.drop_column("generated_article_images", "generation_params")
    op.drop_column("generated_article_images", "negative_prompt")













