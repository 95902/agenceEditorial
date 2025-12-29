"""Pydantic response schemas for API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionResponse(BaseModel):
    """Response schema for workflow execution."""

    execution_id: UUID = Field(..., description="Unique execution ID", examples=["123e4567-e89b-12d3-a456-426614174000"])
    status: str = Field(..., description="Execution status (pending, running, completed, failed)", examples=["pending"])
    start_time: Optional[datetime] = Field(None, description="Start time", examples=["2025-01-09T18:00:00Z"])
    estimated_duration_minutes: Optional[int] = Field(None, description="Estimated duration in minutes", examples=[10])
    
    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "pending",
                "start_time": "2025-01-09T18:00:00Z",
                "estimated_duration_minutes": 10
            }
        }


class SiteProfileResponse(BaseModel):
    """Response schema for site profile."""

    domain: str
    analysis_date: datetime
    language_level: Optional[str] = None
    editorial_tone: Optional[str] = None
    target_audience: Optional[Dict[str, Any]] = None
    activity_domains: Optional[Dict[str, Any]] = None
    content_structure: Optional[Dict[str, Any]] = None
    keywords: Optional[Dict[str, Any]] = None
    style_features: Optional[Dict[str, Any]] = None
    pages_analyzed: int
    llm_models_used: Optional[Dict[str, Any]] = None


class SiteListResponse(BaseModel):
    """Response schema for site list."""

    sites: List[SiteProfileResponse]
    total: int


class CompetitorResponse(BaseModel):
    """Response schema for competitor."""

    domain: str
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class CompetitorListResponse(BaseModel):
    """Response schema for competitor list."""

    competitors: List[CompetitorResponse]
    total: int


class ArticleResponse(BaseModel):
    """Response schema for article (T105 - US5)."""

    id: int = Field(..., description="Article ID")
    domain: str = Field(..., description="Domain name")
    url: str = Field(..., description="Article URL")
    title: str = Field(..., description="Article title")
    author: Optional[str] = Field(None, description="Article author")
    published_date: Optional[datetime] = Field(None, description="Publication date")
    word_count: int = Field(..., description="Word count")
    created_at: datetime = Field(..., description="Creation timestamp")


class ArticleListResponse(BaseModel):
    """Response schema for article list (T105 - US5)."""

    articles: List[ArticleResponse] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


class TopicResponse(BaseModel):
    """Response schema for topic."""

    id: int
    keywords: List[str]
    name: str
    size: int
    coherence: float


class TopicsResponse(BaseModel):
    """Response schema for topics."""

    topics: List[TopicResponse]
    total: int
    time_window_days: int


class GapResponse(BaseModel):
    """Response schema for content gap."""

    topic_id: int
    topic_keywords: List[str]
    gap_score: float
    frequency: int
    recommendation: Optional[Dict[str, Any]] = None


class GapsResponse(BaseModel):
    """Response schema for gaps analysis."""

    gaps: List[GapResponse]
    total: int


class SiteHistoryEntry(BaseModel):
    """Response schema for a single historical analysis entry."""

    analysis_date: datetime
    language_level: Optional[str] = None
    editorial_tone: Optional[str] = None
    pages_analyzed: int
    target_audience: Optional[Dict[str, Any]] = None
    activity_domains: Optional[Dict[str, Any]] = None
    content_structure: Optional[Dict[str, Any]] = None
    keywords: Optional[Dict[str, Any]] = None
    style_features: Optional[Dict[str, Any]] = None


class MetricComparison(BaseModel):
    """Response schema for metric comparison between time periods."""

    metric_name: str
    current_value: Any
    previous_value: Optional[Any] = None
    change: Optional[float] = None  # Percentage change
    trend: Optional[str] = None  # "increasing", "decreasing", "stable"


class SiteHistoryResponse(BaseModel):
    """Response schema for site analysis history."""

    domain: str
    total_analyses: int
    history: List[SiteHistoryEntry]
    metric_comparisons: Optional[List[MetricComparison]] = None
    first_analysis_date: Optional[datetime] = None
    last_analysis_date: Optional[datetime] = None


# ============================================================
# Error Response Schema
# ============================================================

class ErrorResponse(BaseModel):
    """Response schema for errors."""

    error: str
    detail: Optional[str] = None
    execution_id: Optional[UUID] = None


# ============================================================
# Site Audit Response Schemas
# ============================================================

class DomainDetail(BaseModel):
    """Response schema for activity domain detail."""

    id: str = Field(..., description="Domain slug identifier")
    label: str = Field(..., description="Domain label")
    confidence: int = Field(..., description="Confidence score (0-100)", ge=0, le=100)
    topics_count: int = Field(..., description="Number of relevant topic clusters from trend pipeline for this domain", ge=0)
    summary: str = Field(..., description="Domain summary description")


class WorkflowStep(BaseModel):
    """Response schema for workflow step status."""

    step: int = Field(..., description="Step number")
    name: str = Field(..., description="Step name")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        ..., description="Step status"
    )
    execution_id: Optional[str] = Field(None, description="Execution ID for this step")


class WorkflowStepDetail(BaseModel):
    """Détails d'une étape de workflow avec progression."""

    step: int = Field(..., description="Numéro de l'étape")
    name: str = Field(..., description="Nom de l'étape")
    workflow_type: str = Field(..., description="Type de workflow")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        ..., description="Statut de l'étape"
    )
    execution_id: Optional[str] = Field(None, description="ID d'exécution")
    start_time: Optional[datetime] = Field(None, description="Heure de début")
    end_time: Optional[datetime] = Field(None, description="Heure de fin")
    duration_seconds: Optional[int] = Field(None, description="Durée en secondes")
    error_message: Optional[str] = Field(None, description="Message d'erreur si échec")
    progress_percentage: Optional[float] = Field(
        None,
        description="Pourcentage de progression (0-100)",
        ge=0,
        le=100,
    )


class DataStatus(BaseModel):
    """Response schema for data availability status."""

    has_profile: bool = Field(..., description="Site profile exists")
    has_competitors: bool = Field(..., description="Competitors data exists")
    has_client_articles: bool = Field(..., description="Client articles exist")
    has_competitor_articles: bool = Field(..., description="Competitor articles exist")
    has_trend_pipeline: bool = Field(..., description="Trend pipeline data exists")


class PendingAuditResponse(BaseModel):
    """Response schema for pending audit (workflows in progress)."""

    status: Literal["pending"] = Field(..., description="Status is pending")
    execution_id: str = Field(..., description="Orchestrator execution ID")
    message: str = Field(..., description="Status message")
    workflow_steps: List[WorkflowStep] = Field(..., description="List of workflow steps")
    data_status: DataStatus = Field(..., description="Current data availability status")


class SiteAuditResponse(BaseModel):
    """Response schema for complete site audit."""

    url: str = Field(..., description="Site URL")
    profile: Dict[str, Any] = Field(
        ...,
        description="Site profile with style and themes",
        example={
            "style": {
                "tone": "professionnel",
                "vocabulary": "spécialisé en technologie",
                "format": "articles longs (1500-2500 mots)",
            },
            "themes": ["Cloud Computing", "Cybersécurité"],
        },
    )
    domains: List[DomainDetail] = Field(..., description="Activity domains with details")
    audience: Dict[str, Any] = Field(
        ...,
        description="Target audience information",
        example={
            "type": "Professionnels IT",
            "level": "Intermédiaire à Expert",
            "sectors": ["Entreprises", "Startups Tech", "DSI"],
        },
    )
    competitors: List[Dict[str, Any]] = Field(
        ...,
        description="List of competitors",
        example=[{"name": "TechNews.fr", "similarity": 85}],
    )
    took_ms: int = Field(..., description="Analysis duration in milliseconds", ge=0)


class AuditStatusResponse(BaseModel):
    """Réponse pour le statut global de l'audit."""

    orchestrator_execution_id: str = Field(..., description="ID de l'orchestrator")
    domain: str = Field(..., description="Domaine analysé")
    overall_status: Literal["pending", "running", "completed", "failed", "partial"] = Field(
        ..., description="Statut global"
    )
    overall_progress: float = Field(
        ...,
        description="Progression globale (0-100)",
        ge=0,
        le=100,
    )
    total_steps: int = Field(..., description="Nombre total d'étapes")
    completed_steps: int = Field(..., description="Nombre d'étapes complétées")
    failed_steps: int = Field(..., description="Nombre d'étapes échouées")
    running_steps: int = Field(..., description="Nombre d'étapes en cours")
    pending_steps: int = Field(..., description="Nombre d'étapes en attente")
    workflow_steps: List[WorkflowStepDetail] = Field(
        ...,
        description="Détails de chaque étape",
    )
    start_time: Optional[datetime] = Field(None, description="Heure de début globale")
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimation de fin",
    )
    data_status: DataStatus = Field(..., description="Statut des données")


# ============================================================
# Topics by Domain Response Schemas
# ============================================================

class TopicEngagement(BaseModel):
    """Engagement metrics for a topic."""

    views: Optional[int] = Field(None, description="Number of views", examples=[1250])
    shares: Optional[int] = Field(None, description="Number of shares", examples=[45])


class TopicDetail(BaseModel):
    """Detailed topic information for frontend."""

    id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing dans le cloud hybride"])
    summary: str = Field(..., description="Topic summary", examples=["Analyse des tendances émergentes..."])
    keywords: List[str] = Field(..., description="Topic keywords", examples=[["edge computing", "cloud hybride"]])
    publish_date: Optional[str] = Field(None, description="Most recent publication date (YYYY-MM-DD)", examples=["2024-09-20"])
    read_time: Optional[str] = Field(None, description="Estimated read time", examples=["8 min"])
    engagement: Optional[TopicEngagement] = Field(None, description="Engagement metrics (optional)")
    category: Optional[str] = Field(None, description="Topic category/scope", examples=["Infrastructure"])
    relevance_score: Optional[int] = Field(None, description="Relevance score (0-100)", examples=[95])
    trend: Optional[str] = Field(None, description="Trend direction: up, stable, down", examples=["up"])
    sources: Optional[List[str]] = Field(None, description="Source domains", examples=[["AWS Blog", "TechCrunch"]])


class DomainTopicsResponse(BaseModel):
    """Response schema for topics by domain."""

    domain: str = Field(..., description="Activity domain", examples=["cyber"])
    count: int = Field(..., description="Number of topics", examples=[5])
    topics: List[TopicDetail] = Field(..., description="List of topics")


# ============================================================
# Topic Details Response Schemas
# ============================================================

class CompetitorDetail(BaseModel):
    """Competitor article detail."""

    name: str = Field(..., description="Competitor domain name", examples=["TechNews.fr"])
    title: str = Field(..., description="Article title", examples=["Edge Computing : La révolution de l'informatique distribuée"])
    published_date: Optional[str] = Field(None, description="Publication date (YYYY-MM-DD)", examples=["2024-09-18"])
    performance: Optional[Dict[str, Any]] = Field(None, description="Performance metrics (optional)", examples=[{"views": 2500, "shares": 89, "engagement": "Élevé"}])
    strengths: Optional[List[str]] = Field(None, description="Article strengths (optional)", examples=[["Exemples concrets", "Schémas techniques"]])
    weaknesses: Optional[List[str]] = Field(None, description="Article weaknesses (optional)", examples=[["Manque de cas d'usage enterprise"]])


class AngleDetail(BaseModel):
    """Editorial angle detail."""

    angle: str = Field(..., description="Angle title", examples=["Guide pratique d'implémentation"])
    description: str = Field(..., description="Angle description", examples=["Comment implémenter l'edge computing étape par étape"])
    differentiation: Optional[str] = Field(None, description="Differentiation strategy (optional)", examples=["Plus pratique et actionnable que les concurrents"])
    potential: Optional[str] = Field(None, description="Potential level: Élevé, Moyen, Faible (optional)", examples=["Élevé"])


class SourceDetail(BaseModel):
    """Source detail."""

    name: str = Field(..., description="Source domain name", examples=["AWS Blog"])
    type: Optional[str] = Field(None, description="Source type (optional)", examples=["Documentation officielle"])
    credibility: Optional[str] = Field(None, description="Credibility level (optional)", examples=["Très élevée"])
    last_update: Optional[str] = Field(None, description="Last update date (YYYY-MM-DD) (optional)", examples=["2024-09-20"])
    relevant_content: Optional[str] = Field(None, description="Relevant content description (optional)", examples=["Guide d'architecture edge computing"])


class TopicPredictions(BaseModel):
    """Topic performance predictions."""

    views: Optional[str] = Field(None, description="Predicted views range", examples=["2,500 - 4,000"])
    shares: Optional[str] = Field(None, description="Predicted shares range", examples=["50 - 80"])
    writing_time: Optional[str] = Field(None, description="Estimated writing time", examples=["2-3 heures"])
    difficulty: Optional[str] = Field(None, description="Difficulty level", examples=["Intermédiaire"])


class TrendDetail(BaseModel):
    """Trend information."""

    label: str = Field(..., description="Trend label (En hausse, Stable, En baisse)", examples=["En hausse"])
    delta: Optional[str] = Field(None, description="Trend delta description (optional)", examples=["+35% de recherches sur ce sujet dans les 30 derniers jours"])


class TopicDetailsResponse(BaseModel):
    """Response schema for topic details."""

    id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing dans le cloud hybride"])
    publish_date: Optional[str] = Field(None, description="Most recent publication date (YYYY-MM-DD)", examples=["2024-09-20"])
    read_time: Optional[str] = Field(None, description="Estimated read time", examples=["8 min"])
    relevance_score: Optional[int] = Field(None, description="Relevance score (0-100)", examples=[95])
    category: Optional[str] = Field(None, description="Topic category/scope", examples=["Infrastructure"])
    summary: str = Field(..., description="Topic summary", examples=["Analyse des tendances émergentes de l'edge computing..."])
    keywords: List[str] = Field(..., description="Topic keywords", examples=[["edge computing", "cloud hybride", "latence"]])
    key_points: Optional[List[str]] = Field(None, description="Key points from article outline (optional)", examples=[["Définition et principe de l'edge computing", "Avantages par rapport au cloud centralisé"]])
    competitors: Optional[List[CompetitorDetail]] = Field(None, description="Competitor articles (optional)")
    angles: Optional[List[AngleDetail]] = Field(None, description="Editorial angles (optional)")
    sources: Optional[List[SourceDetail]] = Field(None, description="Sources (optional)")
    predictions: Optional[TopicPredictions] = Field(None, description="Predictions (optional)")
    trend: Optional[TrendDetail] = Field(None, description="Trend information (optional)")

