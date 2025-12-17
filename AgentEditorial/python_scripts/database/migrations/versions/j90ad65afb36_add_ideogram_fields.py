"""Add Ideogram-specific fields to generated_article_images.

Revision ID: j90ad65afb36
Revises: i80ad65afb35
Create Date: 2025-12-20 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "j90ad65afb36"
down_revision: Union[str, None] = "i80ad65afb35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Ideogram-specific fields to generated_article_images."""
    
    # Ajouter provider (ideogram ou local)
    op.add_column(
        "generated_article_images",
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="ideogram"),
    )
    
    # Ajouter ideogram_url (URL originale Ideogram)
    op.add_column(
        "generated_article_images",
        sa.Column("ideogram_url", sa.Text(), nullable=True),
    )
    
    # Ajouter magic_prompt (Prompt amélioré par Ideogram)
    op.add_column(
        "generated_article_images",
        sa.Column("magic_prompt", sa.Text(), nullable=True),
    )
    
    # Ajouter style_type (DESIGN, ILLUSTRATION, REALISTIC, GENERAL)
    op.add_column(
        "generated_article_images",
        sa.Column("style_type", sa.String(length=20), nullable=True),
    )
    
    # Ajouter aspect_ratio (1:1, 4:3, 16:9, etc.)
    op.add_column(
        "generated_article_images",
        sa.Column("aspect_ratio", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Remove Ideogram-specific fields from generated_article_images."""
    
    # Supprimer les colonnes
    op.drop_column("generated_article_images", "aspect_ratio")
    op.drop_column("generated_article_images", "style_type")
    op.drop_column("generated_article_images", "magic_prompt")
    op.drop_column("generated_article_images", "ideogram_url")
    op.drop_column("generated_article_images", "provider")


