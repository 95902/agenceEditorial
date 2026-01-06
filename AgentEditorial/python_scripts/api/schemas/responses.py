"""Pydantic response schemas for API endpoints."""

from datetime import datetime
from enum import Enum
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

class IssueSeverity(str, Enum):
    """Severité d'un problème détecté dans l'audit."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueCode(str, Enum):
    """Codes d'erreur structurés pour les problèmes détectés."""

    # Confiance faible
    LOW_CONFIDENCE = "LOW_CONFIDENCE"

    # Pollution boilerplate
    BOILERPLATE_DETECTED = "BOILERPLATE_DETECTED"
    DUPLICATE_KEYWORDS = "DUPLICATE_KEYWORDS"

    # LLM incomplet
    LLM_PARSE_FAILED = "LLM_PARSE_FAILED"
    MISSING_OPPORTUNITIES = "MISSING_OPPORTUNITIES"
    MISSING_SATURATED_ANGLES = "MISSING_SATURATED_ANGLES"

    # Incohérences
    TOPICS_COUNT_MISMATCH = "TOPICS_COUNT_MISMATCH"
    MISSING_FRESHNESS = "MISSING_FRESHNESS"

    # Qualité des données
    INSUFFICIENT_ARTICLES = "INSUFFICIENT_ARTICLES"
    NO_COMPETITORS = "NO_COMPETITORS"


class AuditIssue(BaseModel):
    """Problème détecté dans l'audit avec suggestion de résolution."""

    code: IssueCode = Field(..., description="Code d'erreur structuré")
    severity: IssueSeverity = Field(..., description="Niveau de sévérité")
    message: str = Field(..., description="Description du problème")
    suggestion: str = Field(..., description="Suggestion de résolution")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel (domaines affectés, valeurs, etc.)")


class TopicSummary(BaseModel):
    """Summary schema for topic in domain details."""

    id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing dans le cloud hybride"])
    summary: str = Field(..., description="Topic summary", examples=["Analyse des tendances émergentes..."])
    keywords: List[str] = Field(..., description="Topic keywords", examples=[["edge computing", "cloud hybride"]])
    relevance_score: Optional[int] = Field(None, description="Relevance score (0-100)", examples=[95], ge=0, le=100)
    trend: Optional[str] = Field(None, description="Trend direction: up, stable, down", examples=["up"])
    category: Optional[str] = Field(None, description="Topic category/scope", examples=["Infrastructure"])


class DomainMetrics(BaseModel):
    """Metrics for an activity domain."""

    total_articles: int = Field(..., description="Total number of articles for this domain", ge=0)
    trending_topics: int = Field(..., description="Number of trending topics", ge=0)
    avg_relevance: float = Field(..., description="Average relevance score", ge=0.0)
    top_keywords: List[str] = Field(..., description="Top keywords for this domain", default_factory=list)


class DomainDetail(BaseModel):
    """Response schema for activity domain detail."""

    id: str = Field(..., description="Domain slug identifier")
    label: str = Field(..., description="Domain label")
    confidence: int = Field(..., description="Confidence score (0-100)", ge=0, le=100)
    confidence_normalized: Optional[float] = Field(None, description="Confidence normalized to 0-1 scale", ge=0, le=1)
    confidence_label: Optional[str] = Field(None, description="Human-readable confidence level (Très faible, Faible, Moyenne, Élevée, Très élevée)")
    topics_count: int = Field(..., description="Number of relevant topic clusters from trend pipeline for this domain", ge=0)
    summary: str = Field(..., description="Domain summary description")
    topics: Optional[List[TopicSummary]] = Field(None, description="List of topics for this domain (if include_topics=True)")
    metrics: Optional[DomainMetrics] = Field(None, description="Aggregated metrics for this domain")


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


class TrendingTopic(BaseModel):
    """Trending topic information."""

    id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing"])
    category: Optional[str] = Field(None, description="Topic category/scope", examples=["Infrastructure"])
    growth_rate: float = Field(..., description="Growth rate percentage", examples=[214.3])
    volume: int = Field(..., description="Article volume", examples=[29], ge=0)
    velocity: Optional[float] = Field(None, description="Velocity metric", examples=[0.738916])
    freshness: Optional[float] = Field(None, description="Freshness ratio", examples=[0.045872])
    source_diversity: int = Field(..., description="Number of different sources", examples=[4], ge=0)
    potential_score: Optional[float] = Field(None, description="Potential score (0-1)", examples=[0.4331], ge=0.0, le=1.0)
    keywords: List[str] = Field(..., description="Topic keywords", default_factory=list)
    related_domain: Optional[str] = Field(None, description="Related activity domain", examples=["Enterprise services"])


class TrendingTopicsSection(BaseModel):
    """Section for trending topics."""

    title: str = Field(default="Tendances en hausse", description="Section title")
    description: str = Field(default="Topics avec la plus forte croissance", description="Section description")
    topics: List[TrendingTopic] = Field(..., description="List of trending topics")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")


class SaturatedAngle(BaseModel):
    """Saturated editorial angle."""

    angle: str = Field(..., description="Angle title", examples=["Guide pratique"])
    frequency: str = Field(..., description="Frequency level", examples=["Moyenne"])
    reason: Optional[str] = Field(None, description="Reason for saturation")


class EditorialOpportunityDetail(BaseModel):
    """Editorial opportunity detail in trend analysis."""

    angle: str = Field(..., description="Opportunity angle", examples=["Guide pratique d'implémentation"])
    potential: str = Field(..., description="Potential level", examples=["Élevé"])
    differentiation: Optional[str] = Field(None, description="Differentiation strategy")
    effort: Optional[str] = Field(None, description="Effort level")


class TrendAnalysisDetail(BaseModel):
    """Detailed trend analysis."""

    topic_id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    topic_title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing"])
    synthesis: str = Field(..., description="LLM-generated synthesis")
    saturated_angles: Optional[List[SaturatedAngle]] = Field(None, description="List of saturated angles")
    opportunities: Optional[List[EditorialOpportunityDetail]] = Field(None, description="List of opportunities")
    llm_model: Optional[str] = Field(None, description="LLM model used", examples=["phi3:medium"])
    generated_at: Optional[datetime] = Field(None, description="Generation timestamp")


class TrendAnalysesSection(BaseModel):
    """Section for trend analyses."""

    title: str = Field(default="Analyses de tendances", description="Section title")
    description: str = Field(default="Synthèses générées par IA sur les tendances", description="Section description")
    analyses: List[TrendAnalysisDetail] = Field(..., description="List of trend analyses")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")


class TimeWindow(BaseModel):
    """Time window metrics."""

    period: str = Field(..., description="Time period", examples=["30 derniers jours"])
    volume: int = Field(..., description="Article volume", examples=[29], ge=0)
    velocity: float = Field(..., description="Velocity metric", examples=[0.738916])
    freshness_ratio: Optional[float] = Field(None, description="Freshness ratio", examples=[0.045872])
    trend_direction: str = Field(..., description="Trend direction", examples=["up"])
    drift_detected: bool = Field(..., description="Whether drift was detected", examples=[True])


class TemporalInsight(BaseModel):
    """Temporal insight for a topic."""

    topic_id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    topic_title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing"])
    time_windows: List[TimeWindow] = Field(..., description="Time window metrics", default_factory=list)
    cohesion_score: Optional[float] = Field(None, description="Cohesion score", examples=[0.585545], ge=0.0, le=1.0)
    potential_score: Optional[float] = Field(None, description="Potential score", examples=[0.4331], ge=0.0, le=1.0)
    source_diversity: int = Field(..., description="Number of different sources", examples=[4], ge=0)


class TemporalInsightsSection(BaseModel):
    """Section for temporal insights."""

    title: str = Field(default="Évolution temporelle des tendances", description="Section title")
    description: str = Field(default="Analyse de la croissance et de la fraîcheur des topics", description="Section description")
    insights: List[TemporalInsight] = Field(..., description="List of temporal insights")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")


class EditorialOpportunity(BaseModel):
    """Editorial opportunity (article recommendation)."""

    id: int = Field(..., description="Recommendation ID", examples=[812])
    topic_id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    topic_title: str = Field(..., description="Topic title", examples=["L'avenir de l'edge computing"])
    article_title: str = Field(..., description="Suggested article title", examples=["Revolutionary UX Design"])
    hook: str = Field(..., description="Article hook", examples=["Découvrez la révolutionnaire approche..."])
    effort_level: str = Field(..., description="Effort level", examples=["medium"])
    effort_label: str = Field(..., description="Effort label", examples=["Effort moyen"])
    differentiation_score: Optional[float] = Field(None, description="Differentiation score (0-1)", examples=[0.9], ge=0.0, le=1.0)
    differentiation_label: Optional[str] = Field(None, description="Differentiation label", examples=["Peu différenciant"])
    status: str = Field(..., description="Status", examples=["suggested"])
    status_label: str = Field(..., description="Status label", examples=["Suggéré"])
    outline: Optional[Dict[str, Any]] = Field(None, description="Article outline")
    related_domain: Optional[str] = Field(None, description="Related activity domain", examples=["Enterprise services"])
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class EditorialOpportunitiesSection(BaseModel):
    """Section for editorial opportunities."""

    title: str = Field(default="Opportunités éditoriales", description="Section title")
    description: str = Field(default="Suggestions d'articles générées par IA", description="Section description")
    recommendations: List[EditorialOpportunity] = Field(..., description="List of article recommendations")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")


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
    issues: List[AuditIssue] = Field(
        default_factory=list,
        description="Liste des problèmes détectés dans l'audit avec suggestions de résolution",
    )
    trending_topics: Optional[TrendingTopicsSection] = Field(
        None,
        description="Trending topics section (if include_trending=True)",
    )
    trend_analyses: Optional[TrendAnalysesSection] = Field(
        None,
        description="Trend analyses section (if include_analyses=True)",
    )
    temporal_insights: Optional[TemporalInsightsSection] = Field(
        None,
        description="Temporal insights section (if include_temporal=True)",
    )
    editorial_opportunities: Optional[EditorialOpportunitiesSection] = Field(
        None,
        description="Editorial opportunities section (if include_opportunities=True)",
    )


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

