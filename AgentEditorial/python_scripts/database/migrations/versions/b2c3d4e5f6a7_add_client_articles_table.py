"""Add client_articles table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create client_articles table
    op.create_table(
        'client_articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('site_profile_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('url_hash', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('published_date', sa.Date(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('qdrant_point_id', sa.UUID(), nullable=True),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('duplicate_of', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['site_profile_id'], ['site_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['duplicate_of'], ['client_articles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index('ix_client_articles_site_profile_id', 'client_articles', ['site_profile_id'], unique=False)
    op.create_index('ix_client_articles_url_hash', 'client_articles', ['url_hash'], unique=False)
    op.create_index('ix_client_articles_published_date', 'client_articles', ['published_date'], unique=False)
    op.create_index('ix_client_articles_topic_id', 'client_articles', ['topic_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_client_articles_topic_id', table_name='client_articles')
    op.drop_index('ix_client_articles_published_date', table_name='client_articles')
    op.drop_index('ix_client_articles_url_hash', table_name='client_articles')
    op.drop_index('ix_client_articles_site_profile_id', table_name='client_articles')
    op.drop_table('client_articles')

