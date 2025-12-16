"""Add generated_images table for Z-Image generation.

Revision ID: h70ad65afb34
Revises: aa98bd461802
Create Date: 2025-12-16 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "h70ad65afb34"
down_revision: Union[str, None] = "aa98bd461802"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================================================
    # TABLE: generated_images
    # Table pour stocker les images générées avec Z-Image
    # ===========================================================================
    op.create_table(
        "generated_images",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Identification
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.String(length=32), nullable=False),
        # Fichier
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        # Paramètres de génération
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("guidance_scale", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        # Modèle
        sa.Column("model_used", sa.String(length=100), nullable=False, server_default="z-image-turbo"),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        # Performance
        sa.Column("generation_time_seconds", sa.Numeric(precision=10, scale=2), nullable=True),
        # Métadonnées
        sa.Column("image_type", sa.String(length=50), nullable=True),  # hero, article, social, etc.
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # JSON array de tags
        # Relations
        sa.Column("site_profile_id", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Contraintes
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["site_profile_id"],
            ["site_profiles.id"],
            name="fk_generated_images_site_profile",
        ),
        sa.UniqueConstraint("prompt_hash", name="uq_generated_images_prompt_hash"),
    )

    # Index
    op.create_index("ix_generated_images_domain", "generated_images", ["domain"], unique=False)
    op.create_index("ix_generated_images_prompt_hash", "generated_images", ["prompt_hash"], unique=True)
    op.create_index("ix_generated_images_created_at", "generated_images", ["created_at"], unique=False)
    op.create_index("ix_generated_images_domain_created", "generated_images", ["domain", "created_at"], unique=False)
    op.create_index("ix_generated_images_type_created", "generated_images", ["image_type", "created_at"], unique=False)


def downgrade() -> None:
    # Supprimer les index
    op.drop_index("ix_generated_images_type_created", table_name="generated_images")
    op.drop_index("ix_generated_images_domain_created", table_name="generated_images")
    op.drop_index("ix_generated_images_created_at", table_name="generated_images")
    op.drop_index("ix_generated_images_prompt_hash", table_name="generated_images")
    op.drop_index("ix_generated_images_domain", table_name="generated_images")
    
    # Supprimer la table
    op.drop_table("generated_images")



