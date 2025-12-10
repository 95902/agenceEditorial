"""SQLAlchemy models for all database tables."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from python_scripts.database.db_session import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# 1. site_profiles
class SiteProfile(Base, TimestampMixin, SoftDeleteMixin):
    """Site editorial profile model."""

    __tablename__ = "site_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    analysis_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    language_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    editorial_tone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_audience: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    activity_domains: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    content_structure: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    style_features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pages_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_models_used: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    analysis_results: Mapped[list["SiteAnalysisResult"]] = relationship(
        "SiteAnalysisResult",
        back_populates="site_profile",
        cascade="all, delete-orphan",
    )
    client_articles: Mapped[list["ClientArticle"]] = relationship(
        "ClientArticle",
        back_populates="site_profile",
        cascade="all, delete-orphan",
    )


# 2. workflow_executions
class WorkflowExecution(Base, TimestampMixin, SoftDeleteMixin):
    """Workflow execution tracking model."""

    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
        default=uuid4,
    )
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    was_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    parent_execution_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id"),
        nullable=True,
    )

    # Relationships
    analysis_results: Mapped[list["SiteAnalysisResult"]] = relationship(
        "SiteAnalysisResult",
        back_populates="execution",
        cascade="all, delete-orphan",
    )
    performance_metrics: Mapped[list["PerformanceMetric"]] = relationship(
        "PerformanceMetric",
        back_populates="execution",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="execution",
    )
    error_logs: Mapped[list["ErrorLog"]] = relationship(
        "ErrorLog",
        back_populates="execution",
    )


# 3. site_analysis_results
class SiteAnalysisResult(Base, SoftDeleteMixin):
    """Site analysis results by phase."""

    __tablename__ = "site_analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("site_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_phase: Mapped[str] = mapped_column(String(100), nullable=False)
    phase_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processing_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    site_profile: Mapped["SiteProfile"] = relationship(
        "SiteProfile",
        back_populates="analysis_results",
    )
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="analysis_results",
    )

    __table_args__ = (
        Index("ix_site_analysis_results_profile_phase", "site_profile_id", "analysis_phase"),
    )


# 4. competitor_articles
class CompetitorArticle(Base, TimestampMixin, SoftDeleteMixin):
    """Competitor article model."""

    __tablename__ = "competitor_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    article_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    qdrant_point_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("competitor_articles.id"),
        nullable=True,
    )
    scraping_permission_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scraping_permissions.id"),
        nullable=True,
    )


# 4b. client_articles
class ClientArticle(Base, TimestampMixin, SoftDeleteMixin):
    """Client article model."""

    __tablename__ = "client_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("site_profiles.id"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    article_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    qdrant_point_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("client_articles.id"),
        nullable=True,
    )

    # Relationships
    site_profile: Mapped["SiteProfile"] = relationship(
        "SiteProfile",
        back_populates="client_articles",
    )


# Note: editorial_trends and bertopic_analysis tables removed in migration e40ad65afb31
# These tables were only used by the removed trends router


# 7. topic_clusters (ETAGE 1 - Clustering BERTopic)
class TopicCluster(Base, SoftDeleteMixin):
    """Topic cluster from BERTopic analysis."""

    __tablename__ = "topic_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    top_terms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    centroid_vector_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    coherence_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("analysis_id", "topic_id", name="uq_topic_cluster_analysis_topic"),
        Index("ix_topic_clusters_analysis", "analysis_id"),
    )


# 8. topic_outliers (ETAGE 1 - Documents non-classifiés)
class TopicOutlier(Base, SoftDeleteMixin):
    """Outlier documents from BERTopic analysis (label=-1)."""

    __tablename__ = "topic_outliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(255), nullable=False)
    article_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    potential_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_distance: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_topic_outliers_analysis", "analysis_id"),
    )


# 9. topic_temporal_metrics (ETAGE 2 - Analyse temporelle)
class TopicTemporalMetrics(Base, SoftDeleteMixin):
    """Temporal metrics for topic evolution analysis."""

    __tablename__ = "topic_temporal_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_start: Mapped[datetime] = mapped_column(Date, nullable=False)
    window_end: Mapped[datetime] = mapped_column(Date, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    velocity: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    freshness_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    source_diversity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cohesion_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    potential_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    drift_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    drift_distance: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_topic_temporal_metrics_topic_window", "topic_cluster_id", "window_start"),
    )


# 10. trend_analysis (ETAGE 3 - Synthèse LLM)
class TrendAnalysis(Base, SoftDeleteMixin):
    """LLM-generated trend synthesis and analysis."""

    __tablename__ = "trend_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    synthesis: Mapped[str] = mapped_column(Text, nullable=False)
    saturated_angles: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    opportunities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    llm_model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# 11. article_recommendations (ETAGE 3 - Suggestions d'articles)
class ArticleRecommendation(Base, SoftDeleteMixin):
    """LLM-generated article recommendations."""

    __tablename__ = "article_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    outline: Mapped[dict] = mapped_column(JSONB, nullable=False)
    differentiation_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    effort_level: Mapped[str] = mapped_column(String(50), nullable=False)  # 'easy', 'medium', 'complex'
    status: Mapped[str] = mapped_column(String(50), default="suggested", nullable=False)  # 'suggested', 'approved', 'in_progress', 'published'
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_article_recommendations_status", "status"),
    )


# 12. weak_signals_analysis (ETAGE 3 - Signaux faibles)
class WeakSignalAnalysis(Base, SoftDeleteMixin):
    """Analysis of outlier documents for weak signal detection."""

    __tablename__ = "weak_signals_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    outlier_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    common_thread: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    disruption_potential: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False)  # 'early_adopter', 'wait', 'monitor'
    llm_model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# 13. client_coverage_analysis (ETAGE 4 - Gap Analysis)
class ClientCoverageAnalysis(Base, SoftDeleteMixin):
    """Client coverage analysis per topic."""

    __tablename__ = "client_coverage_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_article_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_score: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    avg_distance_to_centroid: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    analysis_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_client_coverage_domain_topic", "domain", "topic_cluster_id"),
    )


# 14. editorial_gaps (ETAGE 4 - Gaps identifiés)
class EditorialGap(Base, SoftDeleteMixin):
    """Editorial gap identified from coverage analysis."""

    __tablename__ = "editorial_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coverage_score: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    priority_score: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    diagnostic: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_description: Mapped[str] = mapped_column(Text, nullable=False)
    risk_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_editorial_gaps_priority", "priority_score"),
    )


# 15. client_strengths (ETAGE 4 - Avantages compétitifs)
class ClientStrength(Base, SoftDeleteMixin):
    """Client competitive strengths (topics where client outperforms competitors)."""

    __tablename__ = "client_strengths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    topic_cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("topic_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    advantage_score: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# 16. content_roadmap (ETAGE 4 - Plan de contenu)
class ContentRoadmap(Base, SoftDeleteMixin):
    """Content roadmap with prioritized recommendations."""

    __tablename__ = "content_roadmap"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gap_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("editorial_gaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommendation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("article_recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_effort: Mapped[str] = mapped_column(String(50), nullable=False)  # 'easy', 'medium', 'complex'
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # 'pending', 'in_progress', 'completed'
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_content_roadmap_client_priority", "client_domain", "priority_order"),
    )


# 17. trend_pipeline_execution (Orchestration)
class TrendPipelineExecution(Base, SoftDeleteMixin):
    """Trend pipeline execution tracking."""

    __tablename__ = "trend_pipeline_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
        default=uuid4,
    )
    client_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    domains_analyzed: Mapped[dict] = mapped_column(JSONB, nullable=False)
    time_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Étapes du pipeline
    stage_1_clustering_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    stage_2_temporal_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    stage_3_llm_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    stage_4_gap_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    
    # Résultats
    total_articles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_clusters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_outliers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_recommendations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_gaps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Métadonnées
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# 18. crawl_cache
class CrawlCache(Base):
    """Crawl cache model."""

    __tablename__ = "crawl_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cached_content: Mapped[str] = mapped_column(Text, nullable=False)
    cached_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cache_hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# 8. scraping_permissions
class ScrapingPermission(Base, TimestampMixin):
    """Scraping permissions model (robots.txt cache)."""

    __tablename__ = "scraping_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    scraping_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disallowed_paths: Mapped[dict] = mapped_column(JSONB, nullable=False)
    crawl_delay: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_agent_required: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    robots_txt_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cache_expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
    )
    last_fetched: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# 9. performance_metrics
class PerformanceMetric(Base):
    """Performance metrics model."""

    __tablename__ = "performance_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    metric_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    additional_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="performance_metrics",
    )

    __table_args__ = (
        Index("ix_performance_metrics_execution_type", "execution_id", "metric_type"),
    )


# 10. audit_log
class AuditLog(Base):
    """Audit log model."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    step_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    execution: Mapped[Optional["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index("ix_audit_log_execution_timestamp", "execution_id", "timestamp"),
    )


# 11. site_discovery_profiles
class SiteDiscoveryProfile(Base, TimestampMixin):
    """Site discovery profile model for optimized article discovery."""

    __tablename__ = "site_discovery_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)

    # Détection technique
    cms_detected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cms_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_rest_api: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_endpoints: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)

    # Sources de découverte
    sitemap_urls: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    rss_feeds: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    blog_listing_pages: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)

    # Patterns détectés
    url_patterns: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)
    article_url_regex: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pagination_pattern: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sélecteurs CSS optimaux
    content_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statistiques d'efficacité
    total_urls_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_articles_valid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0, nullable=False)
    avg_article_word_count: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Métadonnées
    last_profiled_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    profile_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_sdp_domain", "domain"),
        Index("idx_sdp_cms", "cms_detected"),
        Index("idx_sdp_active", "is_active"),
    )


# 12. url_discovery_scores
class UrlDiscoveryScore(Base):
    """URL discovery score model for article probability scoring."""

    __tablename__ = "url_discovery_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Source de découverte
    discovery_source: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_in: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scoring
    initial_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)

    # Validation
    was_scraped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scrape_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_valid_article: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    validation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hints
    title_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_hint: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    scraped_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("domain", "url_hash", name="unique_url_discovery"),
        Index("idx_uds_domain", "domain"),
        Index("idx_uds_score", "initial_score"),
        Index("idx_uds_source", "discovery_source"),
        Index("idx_uds_valid", "is_valid_article"),
        Index("idx_uds_scraped", "was_scraped"),
    )


# 13. discovery_logs
class DiscoveryLog(Base):
    """Discovery logs model for tracking discovery operations."""

    __tablename__ = "discovery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    execution_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Type d'opération
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Résultats
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    urls_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_valid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Détails
    sources_used: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    errors: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Métadonnées
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_dl_domain", "domain"),
        Index("idx_dl_execution", "execution_id"),
        Index("idx_dl_created", "created_at"),
    )


# 14. error_logs
class ErrorLog(Base):
    """Table de suivi des erreurs pour diagnostic et monitoring."""

    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Contexte
    execution_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    component: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 'qdrant', 'scraping', 'llm', etc.

    # Erreur
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 'AttributeError', 'ValueError', etc.
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contexte additionnel
    context: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)  # URL, collection, article_id, etc.

    # Statut
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="error",
        index=True,
    )  # 'critical', 'error', 'warning'
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Métadonnées
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_occurrence: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_occurrence: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    execution: Mapped[Optional["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="error_logs",
    )

    __table_args__ = (
        Index("idx_error_component_severity", "component", "severity"),
        Index("idx_error_execution", "execution_id", "first_occurrence"),
        Index("idx_error_domain", "domain", "first_occurrence"),
        Index("idx_error_unresolved", "is_resolved", "severity", "first_occurrence"),
    )

