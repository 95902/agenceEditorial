"""Add trend pipeline tables (11 new tables for 4-stage pipeline).

Revision ID: a1b2c3d4e5f6
Revises: 74e1785c0a4b
Create Date: 2025-12-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '74e1785c0a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================================================
    # ÉTAGE 1: Clustering BERTopic + HDBSCAN
    # ===========================================================================
    
    # 1. topic_clusters - Clusters thématiques
    op.create_table(
        'topic_clusters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=500), nullable=False),
        sa.Column('top_terms', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('centroid_vector_id', sa.String(length=255), nullable=True),
        sa.Column('document_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('coherence_score', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', 'topic_id', name='uq_topic_cluster_analysis_topic')
    )
    op.create_index('ix_topic_clusters_analysis', 'topic_clusters', ['analysis_id'], unique=False)
    op.create_index('ix_topic_clusters_created_at', 'topic_clusters', ['created_at'], unique=False)

    # 2. topic_outliers - Documents non-classifiés (label=-1)
    op.create_table(
        'topic_outliers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.String(length=255), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('potential_category', sa.String(length=255), nullable=True),
        sa.Column('embedding_distance', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_topic_outliers_analysis', 'topic_outliers', ['analysis_id'], unique=False)

    # ===========================================================================
    # ÉTAGE 2: Analyse Temporelle
    # ===========================================================================

    # 3. topic_temporal_metrics - Métriques temporelles par topic
    op.create_table(
        'topic_temporal_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.Date(), nullable=False),
        sa.Column('window_end', sa.Date(), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=False),
        sa.Column('velocity', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('freshness_ratio', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('source_diversity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cohesion_score', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('potential_score', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('drift_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('drift_distance', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_topic_temporal_metrics_topic_cluster_id', 'topic_temporal_metrics', ['topic_cluster_id'], unique=False)
    op.create_index('ix_topic_temporal_metrics_topic_window', 'topic_temporal_metrics', ['topic_cluster_id', 'window_start'], unique=False)

    # ===========================================================================
    # ÉTAGE 3: Validation et Enrichissement LLM
    # ===========================================================================

    # 4. trend_analysis - Synthèse LLM des tendances
    op.create_table(
        'trend_analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('synthesis', sa.Text(), nullable=False),
        sa.Column('saturated_angles', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('opportunities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('llm_model_used', sa.String(length=100), nullable=False),
        sa.Column('processing_time_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trend_analysis_topic_cluster_id', 'trend_analysis', ['topic_cluster_id'], unique=False)
    op.create_index('ix_trend_analysis_created_at', 'trend_analysis', ['created_at'], unique=False)

    # 5. article_recommendations - Suggestions d'articles générées par LLM
    op.create_table(
        'article_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('hook', sa.Text(), nullable=False),
        sa.Column('outline', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('differentiation_score', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('effort_level', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='suggested'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_article_recommendations_topic_cluster_id', 'article_recommendations', ['topic_cluster_id'], unique=False)
    op.create_index('ix_article_recommendations_status', 'article_recommendations', ['status'], unique=False)
    op.create_index('ix_article_recommendations_created_at', 'article_recommendations', ['created_at'], unique=False)

    # 6. weak_signals_analysis - Analyse des signaux faibles (outliers)
    op.create_table(
        'weak_signals_analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('outlier_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('common_thread', sa.Text(), nullable=True),
        sa.Column('disruption_potential', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('recommendation', sa.String(length=50), nullable=False),
        sa.Column('llm_model_used', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weak_signals_analysis_analysis_id', 'weak_signals_analysis', ['analysis_id'], unique=False)

    # ===========================================================================
    # ÉTAGE 4: Gap Analysis
    # ===========================================================================

    # 7. client_coverage_analysis - Analyse couverture client par topic
    op.create_table(
        'client_coverage_analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('client_article_count', sa.Integer(), nullable=False),
        sa.Column('coverage_score', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('avg_distance_to_centroid', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('analysis_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_client_coverage_analysis_domain', 'client_coverage_analysis', ['domain'], unique=False)
    op.create_index('ix_client_coverage_analysis_topic_cluster_id', 'client_coverage_analysis', ['topic_cluster_id'], unique=False)
    op.create_index('ix_client_coverage_domain_topic', 'client_coverage_analysis', ['domain', 'topic_cluster_id'], unique=False)
    op.create_index('ix_client_coverage_analysis_date', 'client_coverage_analysis', ['analysis_date'], unique=False)

    # 8. editorial_gaps - Gaps éditoriaux identifiés
    op.create_table(
        'editorial_gaps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_domain', sa.String(length=255), nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('coverage_score', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('priority_score', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('diagnostic', sa.Text(), nullable=False),
        sa.Column('opportunity_description', sa.Text(), nullable=False),
        sa.Column('risk_assessment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_editorial_gaps_client_domain', 'editorial_gaps', ['client_domain'], unique=False)
    op.create_index('ix_editorial_gaps_topic_cluster_id', 'editorial_gaps', ['topic_cluster_id'], unique=False)
    op.create_index('ix_editorial_gaps_priority', 'editorial_gaps', ['priority_score'], unique=False)
    op.create_index('ix_editorial_gaps_created_at', 'editorial_gaps', ['created_at'], unique=False)

    # 9. client_strengths - Avantages compétitifs client
    op.create_table(
        'client_strengths',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('topic_cluster_id', sa.Integer(), nullable=False),
        sa.Column('advantage_score', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['topic_cluster_id'], ['topic_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_client_strengths_domain', 'client_strengths', ['domain'], unique=False)
    op.create_index('ix_client_strengths_topic_cluster_id', 'client_strengths', ['topic_cluster_id'], unique=False)

    # 10. content_roadmap - Plan de contenu priorisé
    op.create_table(
        'content_roadmap',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_domain', sa.String(length=255), nullable=False),
        sa.Column('gap_id', sa.Integer(), nullable=False),
        sa.Column('recommendation_id', sa.Integer(), nullable=False),
        sa.Column('priority_order', sa.Integer(), nullable=False),
        sa.Column('estimated_effort', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['gap_id'], ['editorial_gaps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['article_recommendations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_content_roadmap_client_domain', 'content_roadmap', ['client_domain'], unique=False)
    op.create_index('ix_content_roadmap_client_priority', 'content_roadmap', ['client_domain', 'priority_order'], unique=False)

    # ===========================================================================
    # ORCHESTRATION: Tracking des exécutions du pipeline
    # ===========================================================================

    # 11. trend_pipeline_executions - Suivi des exécutions
    op.create_table(
        'trend_pipeline_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_domain', sa.String(length=255), nullable=True),
        sa.Column('domains_analyzed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('time_window_days', sa.Integer(), nullable=False),
        # Statuts des étapes
        sa.Column('stage_1_clustering_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('stage_2_temporal_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('stage_3_llm_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('stage_4_gap_status', sa.String(length=50), nullable=False, server_default='pending'),
        # Résultats agrégés
        sa.Column('total_articles', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_clusters', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_outliers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_recommendations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_gaps', sa.Integer(), nullable=False, server_default='0'),
        # Métadonnées
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('execution_id', name='uq_trend_pipeline_execution_id')
    )
    op.create_index('ix_trend_pipeline_executions_execution_id', 'trend_pipeline_executions', ['execution_id'], unique=True)
    op.create_index('ix_trend_pipeline_executions_client_domain', 'trend_pipeline_executions', ['client_domain'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order (respect foreign keys)
    op.drop_index('ix_trend_pipeline_executions_client_domain', table_name='trend_pipeline_executions')
    op.drop_index('ix_trend_pipeline_executions_execution_id', table_name='trend_pipeline_executions')
    op.drop_table('trend_pipeline_executions')

    op.drop_index('ix_content_roadmap_client_priority', table_name='content_roadmap')
    op.drop_index('ix_content_roadmap_client_domain', table_name='content_roadmap')
    op.drop_table('content_roadmap')

    op.drop_index('ix_client_strengths_topic_cluster_id', table_name='client_strengths')
    op.drop_index('ix_client_strengths_domain', table_name='client_strengths')
    op.drop_table('client_strengths')

    op.drop_index('ix_editorial_gaps_created_at', table_name='editorial_gaps')
    op.drop_index('ix_editorial_gaps_priority', table_name='editorial_gaps')
    op.drop_index('ix_editorial_gaps_topic_cluster_id', table_name='editorial_gaps')
    op.drop_index('ix_editorial_gaps_client_domain', table_name='editorial_gaps')
    op.drop_table('editorial_gaps')

    op.drop_index('ix_client_coverage_analysis_date', table_name='client_coverage_analysis')
    op.drop_index('ix_client_coverage_domain_topic', table_name='client_coverage_analysis')
    op.drop_index('ix_client_coverage_analysis_topic_cluster_id', table_name='client_coverage_analysis')
    op.drop_index('ix_client_coverage_analysis_domain', table_name='client_coverage_analysis')
    op.drop_table('client_coverage_analysis')

    op.drop_index('ix_weak_signals_analysis_analysis_id', table_name='weak_signals_analysis')
    op.drop_table('weak_signals_analysis')

    op.drop_index('ix_article_recommendations_created_at', table_name='article_recommendations')
    op.drop_index('ix_article_recommendations_status', table_name='article_recommendations')
    op.drop_index('ix_article_recommendations_topic_cluster_id', table_name='article_recommendations')
    op.drop_table('article_recommendations')

    op.drop_index('ix_trend_analysis_created_at', table_name='trend_analysis')
    op.drop_index('ix_trend_analysis_topic_cluster_id', table_name='trend_analysis')
    op.drop_table('trend_analysis')

    op.drop_index('ix_topic_temporal_metrics_topic_window', table_name='topic_temporal_metrics')
    op.drop_index('ix_topic_temporal_metrics_topic_cluster_id', table_name='topic_temporal_metrics')
    op.drop_table('topic_temporal_metrics')

    op.drop_index('ix_topic_outliers_analysis', table_name='topic_outliers')
    op.drop_table('topic_outliers')

    op.drop_index('ix_topic_clusters_created_at', table_name='topic_clusters')
    op.drop_index('ix_topic_clusters_analysis', table_name='topic_clusters')
    op.drop_table('topic_clusters')

