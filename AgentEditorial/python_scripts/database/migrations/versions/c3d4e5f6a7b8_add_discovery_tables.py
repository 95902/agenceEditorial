"""Add discovery tables for enhanced scraping.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-12-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================================================
    # TABLE: site_discovery_profiles
    # Stocke le profil de découverte pour chaque domaine
    # ===========================================================================
    op.create_table(
        'site_discovery_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        
        # Détection technique
        sa.Column('cms_detected', sa.Text(), nullable=True),
        sa.Column('cms_version', sa.Text(), nullable=True),
        sa.Column('has_rest_api', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('api_endpoints', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Sources de découverte
        sa.Column('sitemap_urls', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('rss_feeds', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('blog_listing_pages', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        
        # Patterns détectés
        sa.Column('url_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('article_url_regex', sa.Text(), nullable=True),
        sa.Column('pagination_pattern', sa.Text(), nullable=True),
        
        # Sélecteurs CSS optimaux
        sa.Column('content_selector', sa.Text(), nullable=True),
        sa.Column('title_selector', sa.Text(), nullable=True),
        sa.Column('date_selector', sa.Text(), nullable=True),
        sa.Column('author_selector', sa.Text(), nullable=True),
        sa.Column('image_selector', sa.Text(), nullable=True),
        
        # Statistiques d'efficacité
        sa.Column('total_urls_discovered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_articles_valid', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_rate', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.0'),
        sa.Column('avg_article_word_count', sa.Numeric(precision=10, scale=2), nullable=True),
        
        # Métadonnées
        sa.Column('last_profiled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_crawled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('profile_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain')
    )
    op.create_index('idx_sdp_domain', 'site_discovery_profiles', ['domain'], unique=False)
    op.create_index('idx_sdp_cms', 'site_discovery_profiles', ['cms_detected'], unique=False)
    op.create_index('idx_sdp_active', 'site_discovery_profiles', ['is_active'], unique=False)

    # ===========================================================================
    # TABLE: url_discovery_scores
    # Stocke le score de chaque URL découverte
    # ===========================================================================
    op.create_table(
        'url_discovery_scores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('url_hash', sa.String(length=64), nullable=False),
        
        # Source de découverte
        sa.Column('discovery_source', sa.Text(), nullable=False),
        sa.Column('discovered_in', sa.Text(), nullable=True),
        
        # Scoring
        sa.Column('initial_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('final_score', sa.Integer(), nullable=True),
        sa.Column('score_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Validation
        sa.Column('was_scraped', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('scrape_status', sa.String(length=50), nullable=True),
        sa.Column('is_valid_article', sa.Boolean(), nullable=True),
        sa.Column('validation_reason', sa.Text(), nullable=True),
        
        # Hints
        sa.Column('title_hint', sa.Text(), nullable=True),
        sa.Column('date_hint', sa.TIMESTAMP(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('discovered_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('scraped_at', sa.TIMESTAMP(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'url_hash', name='unique_url_discovery')
    )
    op.create_index('idx_uds_domain', 'url_discovery_scores', ['domain'], unique=False)
    op.create_index('idx_uds_score', 'url_discovery_scores', ['initial_score'], unique=False)
    op.create_index('idx_uds_source', 'url_discovery_scores', ['discovery_source'], unique=False)
    op.create_index('idx_uds_valid', 'url_discovery_scores', ['is_valid_article'], unique=False)
    op.create_index('idx_uds_scraped', 'url_discovery_scores', ['was_scraped'], unique=False)

    # ===========================================================================
    # TABLE: discovery_logs
    # Logs détaillés des opérations de découverte
    # ===========================================================================
    op.create_table(
        'discovery_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Type d'opération
        sa.Column('operation', sa.Text(), nullable=False),
        sa.Column('phase', sa.Text(), nullable=True),
        
        # Résultats
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('urls_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urls_scraped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urls_valid', sa.Integer(), nullable=False, server_default='0'),
        
        # Détails
        sa.Column('sources_used', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('duration_seconds', sa.Numeric(precision=10, scale=2), nullable=True),
        
        # Métadonnées
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_dl_domain', 'discovery_logs', ['domain'], unique=False)
    op.create_index('idx_dl_execution', 'discovery_logs', ['execution_id'], unique=False)
    op.create_index('idx_dl_created', 'discovery_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_dl_created', table_name='discovery_logs')
    op.drop_index('idx_dl_execution', table_name='discovery_logs')
    op.drop_index('idx_dl_domain', table_name='discovery_logs')
    op.drop_table('discovery_logs')
    
    op.drop_index('idx_uds_scraped', table_name='url_discovery_scores')
    op.drop_index('idx_uds_valid', table_name='url_discovery_scores')
    op.drop_index('idx_uds_source', table_name='url_discovery_scores')
    op.drop_index('idx_uds_score', table_name='url_discovery_scores')
    op.drop_index('idx_uds_domain', table_name='url_discovery_scores')
    op.drop_table('url_discovery_scores')
    
    op.drop_index('idx_sdp_active', table_name='site_discovery_profiles')
    op.drop_index('idx_sdp_cms', table_name='site_discovery_profiles')
    op.drop_index('idx_sdp_domain', table_name='site_discovery_profiles')
    op.drop_table('site_discovery_profiles')










