"""add_variant_fields

Revision ID: k00ad65afb37
Revises: j90ad65afb36
Create Date: 2025-12-16 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k00ad65afb37'
down_revision: Union[str, None] = 'j90ad65afb36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter les colonnes pour le groupement des variantes
    op.add_column('generated_article_images', sa.Column('variant_group_id', sa.String(length=50), nullable=True))
    op.add_column('generated_article_images', sa.Column('variant_number', sa.Integer(), nullable=True))
    op.add_column('generated_article_images', sa.Column('is_selected', sa.Boolean(), nullable=False, server_default='false'))
    
    # Créer un index sur variant_group_id pour les requêtes de groupe
    op.create_index('ix_generated_article_images_variant_group_id', 'generated_article_images', ['variant_group_id'])
    
    # Créer un index composé sur (variant_group_id, variant_number) pour performance
    op.create_index('ix_generated_article_images_variant_group_number', 'generated_article_images', ['variant_group_id', 'variant_number'])


def downgrade() -> None:
    # Supprimer les index
    op.drop_index('ix_generated_article_images_variant_group_number', table_name='generated_article_images')
    op.drop_index('ix_generated_article_images_variant_group_id', table_name='generated_article_images')
    
    # Supprimer les colonnes
    op.drop_column('generated_article_images', 'is_selected')
    op.drop_column('generated_article_images', 'variant_number')
    op.drop_column('generated_article_images', 'variant_group_id')













