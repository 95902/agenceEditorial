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


# 5. editorial_trends
class EditorialTrend(Base, SoftDeleteMixin):
    """Editorial trends model."""

    __tablename__ = "editorial_trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    trend_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trend_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    time_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_editorial_trends_domain_date_type", "domain", "analysis_date", "trend_type"),
    )


# 6. bertopic_analysis
class BertopicAnalysis(Base, SoftDeleteMixin):
    """BERTopic analysis model."""

    __tablename__ = "bertopic_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    time_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    domains_included: Mapped[dict] = mapped_column(JSONB, nullable=False)
    topics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    topic_hierarchy: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    topics_over_time: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    visualizations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_parameters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# 7. crawl_cache
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

