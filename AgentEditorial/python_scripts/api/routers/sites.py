"""API router for site analysis endpoints."""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import SiteAnalysisRequest
from python_scripts.api.schemas.responses import (
    AuditStatusResponse,
    DataStatus,
    DomainDetail,
    DomainMetrics,
    DomainTopicsResponse,
    EditorialOpportunity,
    EditorialOpportunitiesSection,
    ErrorResponse,
    ExecutionResponse,
    MetricComparison,
    PendingAuditResponse,
    SiteAuditResponse,
    SiteHistoryEntry,
    SiteHistoryResponse,
    SiteProfileResponse,
    TemporalInsight,
    TemporalInsightsSection,
    TopicDetail,
    TopicDetailsResponse,
    TopicEngagement,
    TopicSummary,
    TrendAnalysisDetail,
    TrendAnalysesSection,
    TrendingTopic,
    TrendingTopicsSection,
    WorkflowStep,
    WorkflowStepDetail,
)
from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.database.crud_llm_results import (
    get_article_recommendations_by_topic_cluster,
    get_trend_analyses_by_topic_cluster,
)
from python_scripts.database.crud_profiles import (
    get_site_profile_by_domain,
    get_site_history,
    list_site_profiles,
    update_site_profile,
)
from python_scripts.database.crud_temporal_metrics import get_temporal_metrics_by_topic_cluster
from python_scripts.database.models import (
    ArticleRecommendation,
    ClientArticle,
    CompetitorArticle,
    SiteProfile,
    TopicCluster,
    TopicTemporalMetrics,
    TrendAnalysis,
    TrendPipelineExecution,
)
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def _safe_json_field(value: Any) -> Optional[Dict[str, Any]]:
    """
    Safely convert a JSON field value to a dictionary.
    
    Handles cases where the value might be:
    - None -> return None
    - Already a dict -> return as-is
    - A JSON string -> try to parse
    - A malformed/truncated string -> return empty dict with error info
    
    Args:
        value: The value to convert
        
    Returns:
        A dictionary or None
    """
    if value is None:
        return None
    
    if isinstance(value, dict):
        return value
    
    if isinstance(value, str):
        value_stripped = value.strip()
        if value_stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value_stripped)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"items": parsed}
                return {"value": parsed}
            except json.JSONDecodeError:
                # Malformed JSON - return empty dict with raw value indicator
                logger.warning(
                    "Malformed JSON field detected",
                    value_preview=value[:100] if len(value) > 100 else value,
                )
                return {"_raw_malformed": value[:200] if len(value) > 200 else value}
        # Not JSON-like string
        return {"value": value}
    
    # Other types - wrap in dict
    return {"value": str(value)}


# ============================================================
# Audit utility functions
# ============================================================

def _map_language_level_to_vocabulary(language_level: Optional[str]) -> str:
    """
    Map language_level to vocabulary description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Vocabulary description
    """
    if not language_level:
        return "langage technique"
    
    mapping = {
        "simple": "langage accessible",
        "intermediate": "langage technique",
        "advanced": "spécialisé en technologie",
        "expert": "très spécialisé",
    }
    
    return mapping.get(language_level.lower(), "langage technique")


def _calculate_article_format(content_structure: Optional[Dict[str, Any]]) -> str:
    """
    Calculate article format from content_structure.
    
    Args:
        content_structure: Content structure dictionary
        
    Returns:
        Format description
    """
    if not content_structure or not isinstance(content_structure, dict):
        return "articles moyens (1000-2000 mots)"
    
    avg_word_count = content_structure.get("average_word_count")
    if not avg_word_count or not isinstance(avg_word_count, (int, float)):
        return "articles moyens (1000-2000 mots)"
    
    if avg_word_count < 1000:
        return "articles courts (< 1000 mots)"
    elif avg_word_count <= 2000:
        return "articles moyens (1000-2000 mots)"
    else:
        return "articles longs (1500-2500 mots)"


def _map_language_level_to_audience_level(language_level: Optional[str]) -> str:
    """
    Map language_level to audience level description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Audience level description
    """
    if not language_level:
        return "Intermédiaire"
    
    mapping = {
        "simple": "Débutant",
        "intermediate": "Intermédiaire",
        "advanced": "Intermédiaire à Expert",
        "expert": "Expert",
    }
    
    return mapping.get(language_level.lower(), "Intermédiaire")


def _extract_audience_sectors(target_audience: Optional[Dict[str, Any]]) -> List[str]:
    """
    Extract sectors from target_audience.
    
    Args:
        target_audience: Target audience dictionary
        
    Returns:
        List of sectors
    """
    if not target_audience or not isinstance(target_audience, dict):
        return []
    
    # Try secondary first
    secondary = target_audience.get("secondary")
    if isinstance(secondary, list):
        return secondary
    
    # Try sectors field
    sectors = target_audience.get("sectors")
    if isinstance(sectors, list):
        return sectors
    
    # Try demographics.sectors
    demographics = target_audience.get("demographics", {})
    if isinstance(demographics, dict):
        demo_sectors = demographics.get("sectors")
        if isinstance(demo_sectors, list):
            return demo_sectors
    
    return []


def _slugify(text: str) -> str:
    """
    Convert text to slug format.
    
    Args:
        text: Text to slugify
        
    Returns:
        Slug string
    """
    import re
    
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text


def _count_articles_for_domain(
    articles: List[Any], domain_label: str
) -> int:
    """
    Count articles that match a domain label.
    
    Uses heuristics: check if domain keywords appear in article title or keywords.
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label to match
        
    Returns:
        Count of matching articles
    """
    if not articles or not domain_label:
        return 0
    
    # Extract keywords from domain label
    domain_keywords = set(domain_label.lower().split())
    
    count = 0
    for article in articles:
        # Check title
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            count += 1
            continue
        
        # Check keywords field
        if hasattr(article, "keywords") and article.keywords:
            keywords = article.keywords
            if isinstance(keywords, dict):
                primary_keywords = keywords.get("primary_keywords", [])
                if isinstance(primary_keywords, list):
                    keywords_str = " ".join(str(k).lower() for k in primary_keywords)
                    if any(keyword in keywords_str for keyword in domain_keywords if len(keyword) > 3):
                        count += 1
                        continue
    
    return count


async def _count_topics_for_domain(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any],
    domain_label: str,
) -> int:
    """
    Count topic clusters relevant to a domain from trend pipeline.
    
    Uses the same logic as _get_topics_by_domain to determine relevance.
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional)
        domain_label: Domain label to match
        
    Returns:
        Count of relevant topic clusters (0 if no trend pipeline)
    """
    if not trend_execution:
        return 0
    
    from sqlalchemy import select
    from python_scripts.database.models import ClientArticle, CompetitorArticle
    from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis
    
    # Get all clusters from trend pipeline
    clusters = await get_topic_clusters_by_analysis(
        db,
        trend_execution.id,
        scope=None,
        only_valid=True,
    )
    
    if not clusters:
        return 0
    
    # Get all articles (client + competitor) for matching
    all_client_articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    all_client_articles_result = await db.execute(all_client_articles_stmt)
    all_client_articles = list(all_client_articles_result.scalars().all())
    
    all_competitor_articles_stmt = (
        select(CompetitorArticle)
        .where(
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
        .limit(5000)  # Limit for performance
    )
    all_competitor_articles_result = await db.execute(all_competitor_articles_stmt)
    all_competitor_articles = list(all_competitor_articles_result.scalars().all())
    
    all_articles = all_client_articles + all_competitor_articles
    
    # Count relevant clusters
    relevant_count = 0
    
    for cluster in clusters:
        # Get articles for this cluster
        cluster_articles_by_topic = [
            art for art in all_articles
            if art.topic_id == cluster.topic_id
        ]
        
        cluster_articles = []
        if cluster_articles_by_topic:
            cluster_articles = cluster_articles_by_topic
        elif cluster.document_ids:
            doc_ids = cluster.document_ids.get("ids", []) or []
            if isinstance(doc_ids, list):
                doc_ids_str = {str(doc_id).lower() for doc_id in doc_ids}
                cluster_articles_by_point = [
                    art for art in all_articles
                    if art.qdrant_point_id and str(art.qdrant_point_id).lower() in doc_ids_str
                ]
                cluster_articles = cluster_articles_by_point
        
        # Check if cluster is relevant to domain
        client_cluster_articles = [
            art for art in cluster_articles
            if isinstance(art, ClientArticle) and art.site_profile_id == profile.id
        ]
        matching_count = _count_articles_for_domain(client_cluster_articles, domain_label)
        
        # Fallback: check cluster metadata or competitor articles
        if matching_count == 0:
            domain_keywords = set(domain_label.lower().split())
            domain_keywords = {kw for kw in domain_keywords if len(kw) > 3}
            
            label_lower = cluster.label.lower() if cluster.label else ""
            top_terms = cluster.top_terms.get("terms", []) if cluster.top_terms else []
            top_terms_str = " ".join(str(t).lower() for t in top_terms[:15])
            
            cluster_matches = any(
                keyword in label_lower or keyword in top_terms_str
                for keyword in domain_keywords
            )
            
            if not cluster_matches and cluster_articles:
                competitor_articles = [
                    art for art in cluster_articles
                    if isinstance(art, CompetitorArticle)
                ]
                if competitor_articles:
                    competitor_matching_count = _count_articles_for_domain(competitor_articles, domain_label)
                    if competitor_matching_count > 0:
                        cluster_matches = True
            
            if cluster_matches:
                matching_count = 1
        
        if matching_count > 0:
            relevant_count += 1
    
    return relevant_count


async def _get_topics_for_domain(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any],
    domain_label: str,
    limit: int = 10,
) -> List[TopicSummary]:
    """
    Get topics for a specific domain, returning TopicSummary list.
    
    Reuses the logic from _get_topics_by_domain but returns a simplified list.
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional)
        domain_label: Domain label to match
        limit: Maximum number of topics to return
        
    Returns:
        List of TopicSummary (empty if no trend pipeline or no relevant topics)
    """
    from python_scripts.api.schemas.responses import TopicSummary
    
    if not trend_execution:
        return []
    
    from sqlalchemy import select
    from python_scripts.database.models import ClientArticle, CompetitorArticle
    from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis
    
    # Get all clusters from trend pipeline
    clusters = await get_topic_clusters_by_analysis(
        db,
        trend_execution.id,
        scope=None,
        only_valid=True,
    )
    
    if not clusters:
        return []
    
    # Get all articles (client + competitor) for matching
    all_client_articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    all_client_articles_result = await db.execute(all_client_articles_stmt)
    all_client_articles = list(all_client_articles_result.scalars().all())
    
    all_competitor_articles_stmt = (
        select(CompetitorArticle)
        .where(
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
        .limit(5000)  # Limit for performance
    )
    all_competitor_articles_result = await db.execute(all_competitor_articles_stmt)
    all_competitor_articles = list(all_competitor_articles_result.scalars().all())
    
    all_articles = all_client_articles + all_competitor_articles
    
    # Filter relevant clusters (same logic as _count_topics_for_domain)
    relevant_clusters = []
    
    for cluster in clusters:
        # Get articles for this cluster
        cluster_articles_by_topic = [
            art for art in all_articles
            if art.topic_id == cluster.topic_id
        ]
        
        cluster_articles = []
        if cluster_articles_by_topic:
            cluster_articles = cluster_articles_by_topic
        elif cluster.document_ids:
            doc_ids = cluster.document_ids.get("ids", []) or []
            if isinstance(doc_ids, list):
                doc_ids_str = {str(doc_id).lower() for doc_id in doc_ids}
                cluster_articles_by_point = [
                    art for art in all_articles
                    if art.qdrant_point_id and str(art.qdrant_point_id).lower() in doc_ids_str
                ]
                cluster_articles = cluster_articles_by_point
        
        # Check if cluster is relevant to domain
        client_cluster_articles = [
            art for art in cluster_articles
            if isinstance(art, ClientArticle) and art.site_profile_id == profile.id
        ]
        matching_count = _count_articles_for_domain(client_cluster_articles, domain_label)
        
        # Fallback: check cluster metadata or competitor articles
        if matching_count == 0:
            domain_keywords = set(domain_label.lower().split())
            domain_keywords = {kw for kw in domain_keywords if len(kw) > 3}
            
            label_lower = cluster.label.lower() if cluster.label else ""
            top_terms = cluster.top_terms.get("terms", []) if cluster.top_terms else []
            top_terms_str = " ".join(str(t).lower() for t in top_terms[:15])
            
            cluster_matches = any(
                keyword in label_lower or keyword in top_terms_str
                for keyword in domain_keywords
            )
            
            if not cluster_matches and cluster_articles:
                competitor_articles = [
                    art for art in cluster_articles
                    if isinstance(art, CompetitorArticle)
                ]
                if competitor_articles:
                    competitor_matching_count = _count_articles_for_domain(competitor_articles, domain_label)
                    if competitor_matching_count > 0:
                        cluster_matches = True
            
            if cluster_matches:
                matching_count = 1
        
        if matching_count > 0:
            relevant_clusters.append(cluster)
    
    # Build TopicSummary list for relevant clusters
    topics_list = []
    
    for cluster in relevant_clusters[:limit]:  # Apply limit
        # Get trend analysis (summary)
        trend_analyses = await get_trend_analyses_by_topic_cluster(db, cluster.id)
        synthesis = trend_analyses[0].synthesis if trend_analyses else cluster.label
        
        # Get temporal metrics (for trend and relevance)
        temporal_metrics = await get_temporal_metrics_by_topic_cluster(db, cluster.id)
        latest_metric = temporal_metrics[0] if temporal_metrics else None
        
        # Calculate relevance score from coherence or volume
        relevance_score = None
        if cluster.coherence_score:
            relevance_score = int(float(cluster.coherence_score) * 100)
        elif latest_metric and latest_metric.volume:
            # Normalize volume to 0-100 (assuming max volume around 1000)
            relevance_score = min(100, int((latest_metric.volume / 10)))
        
        # Determine trend
        trend = None
        if latest_metric:
            trend = _determine_trend(float(latest_metric.velocity) if latest_metric.velocity else None)
        
        # Extract keywords from top_terms
        keywords = []
        if cluster.top_terms:
            terms = cluster.top_terms.get("terms", [])
            if isinstance(terms, list):
                # Extract first 5-10 keywords
                keywords = [str(t.get("word", t) if isinstance(t, dict) else t) for t in terms[:10]]
        
        # Build topic summary
        topic_summary = TopicSummary(
            id=_slugify_topic_id(cluster.topic_id, cluster.label),
            title=cluster.label,
            summary=synthesis,
            keywords=keywords,
            relevance_score=relevance_score,
            trend=trend,
            category=cluster.scope,
        )
        
        topics_list.append(topic_summary)
    
    # Sort by relevance_score (descending), then by title
    topics_list.sort(key=lambda t: (-(t.relevance_score or 0), t.title))
    
    return topics_list


async def _get_domain_metrics(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any],
    domain_label: str,
    client_articles: List[ClientArticle],
) -> Optional[DomainMetrics]:
    """
    Calculate aggregated metrics for a domain.
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional)
        domain_label: Domain label
        client_articles: List of client articles
        
    Returns:
        DomainMetrics or None if no trend pipeline
    """
    from python_scripts.api.schemas.responses import DomainMetrics
    
    if not trend_execution:
        return None
    
    # Get topics for this domain
    topics = await _get_topics_for_domain(db, profile, trend_execution, domain_label, limit=10000)
    
    # Count articles for this domain (always available)
    articles_count = _count_articles_for_domain(client_articles, domain_label)
    
    if not topics:
        # Return metrics with article count even if no topics
        return DomainMetrics(
            total_articles=articles_count,
            trending_topics=0,
            avg_relevance=0.0,
            top_keywords=[],
        )
    
    # Count trending topics (velocity > 0.5 or trend == "up")
    trending_count = sum(1 for t in topics if t.trend == "up")
    
    # Calculate average relevance
    relevance_scores = [t.relevance_score for t in topics if t.relevance_score is not None]
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    # Extract top keywords (most frequent across all topics)
    all_keywords = []
    for topic in topics:
        all_keywords.extend(topic.keywords)
    
    # Count keyword frequency
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    top_keywords = [kw for kw, _ in keyword_counts.most_common(10)]
    
    return DomainMetrics(
        total_articles=articles_count,
        trending_topics=trending_count,
        avg_relevance=round(avg_relevance, 1),
        top_keywords=top_keywords,
    )


async def _format_trending_topic(
    db: AsyncSession,
    cluster: TopicCluster,
    profile: SiteProfile,
    trend_execution: TrendPipelineExecution,
) -> Optional[TrendingTopic]:
    """
    Format a TopicCluster with temporal metrics into a TrendingTopic.
    
    Args:
        db: Database session
        cluster: TopicCluster instance
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution instance
        
    Returns:
        TrendingTopic or None if no temporal metrics
    """
    # Get temporal metrics
    temporal_metrics = await get_temporal_metrics_by_topic_cluster(db, cluster.id)
    if not temporal_metrics:
        return None
    
    latest_metric = temporal_metrics[0]
    
    # Check if topic is trending (velocity > 0.5 or potential_score > 80)
    is_trending = False
    if latest_metric.velocity and float(latest_metric.velocity) > 0.5:
        is_trending = True
    elif latest_metric.potential_score and float(latest_metric.potential_score) > 80:
        is_trending = True
    
    if not is_trending:
        return None
    
    # Calculate growth rate from velocity
    growth_rate = 0.0
    if latest_metric.velocity:
        growth_rate = float(latest_metric.velocity) * 100
    
    # Extract keywords
    keywords = []
    if cluster.top_terms:
        terms = cluster.top_terms.get("terms", [])
        if isinstance(terms, list):
            keywords = [str(t.get("word", t) if isinstance(t, dict) else t) for t in terms[:10]]
    
    # Find related domain by checking articles
    related_domain = None
    activity_domains = _safe_json_field(profile.activity_domains) or {}
    primary_domains = activity_domains.get("primary_domains", [])
    
    # Get articles for this topic
    articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.topic_id == cluster.topic_id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
        .limit(10)
    )
    articles_result = await db.execute(articles_stmt)
    articles = list(articles_result.scalars().all())
    
    # Find domain with most matching articles
    domain_counts = {}
    for domain in primary_domains:
        count = _count_articles_for_domain(articles, domain)
        if count > 0:
            domain_counts[domain] = count
    
    if domain_counts:
        related_domain = max(domain_counts.items(), key=lambda x: x[1])[0]
    
    return TrendingTopic(
        id=_slugify_topic_id(cluster.topic_id, cluster.label),
        title=cluster.label,
        category=cluster.scope,
        growth_rate=round(growth_rate, 1),
        volume=latest_metric.volume,
        velocity=float(latest_metric.velocity) if latest_metric.velocity else None,
        freshness=float(latest_metric.freshness_ratio) if latest_metric.freshness_ratio else None,
        source_diversity=latest_metric.source_diversity,
        potential_score=float(latest_metric.potential_score) if latest_metric.potential_score else None,
        keywords=keywords,
        related_domain=related_domain,
    )


async def _get_trending_topics(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any],
    limit: int = 15,
) -> List[TrendingTopic]:
    """
    Get trending topics (topics with high growth).
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional)
        limit: Maximum number of topics to return
        
    Returns:
        List of TrendingTopic sorted by velocity (descending)
    """
    if not trend_execution:
        return []
    
    # Get all clusters
    clusters = await get_topic_clusters_by_analysis(
        db,
        trend_execution.id,
        scope=None,
        only_valid=True,
    )
    
    if not clusters:
        return []
    
    # Format each cluster and filter trending ones
    trending_topics = []
    for cluster in clusters:
        trending_topic = await _format_trending_topic(db, cluster, profile, trend_execution)
        if trending_topic:
            trending_topics.append(trending_topic)
    
    # Sort by velocity (descending), then by potential_score
    trending_topics.sort(
        key=lambda t: (
            -(t.velocity or 0),
            -(t.potential_score or 0),
        )
    )
    
    return trending_topics[:limit]


async def _format_trend_analysis(
    db: AsyncSession,
    trend_analysis: TrendAnalysis,
    cluster: TopicCluster,
) -> TrendAnalysisDetail:
    """
    Format a TrendAnalysis into TrendAnalysisDetail.
    
    Args:
        db: Database session
        trend_analysis: TrendAnalysis instance
        cluster: TopicCluster instance
        
    Returns:
        TrendAnalysisDetail
    """
    from python_scripts.api.schemas.responses import EditorialOpportunityDetail, SaturatedAngle
    
    # Parse saturated_angles
    saturated_angles = None
    if trend_analysis.saturated_angles:
        sat_angles_data = trend_analysis.saturated_angles
        if isinstance(sat_angles_data, dict):
            angles_list = sat_angles_data.get("angles", [])
            if isinstance(angles_list, list):
                saturated_angles = []
                for angle_data in angles_list:
                    if isinstance(angle_data, dict):
                        saturated_angles.append(SaturatedAngle(
                            angle=angle_data.get("angle", ""),
                            frequency=angle_data.get("frequency", "Moyenne"),
                            reason=angle_data.get("reason"),
                        ))
                    elif isinstance(angle_data, str):
                        saturated_angles.append(SaturatedAngle(
                            angle=angle_data,
                            frequency="Moyenne",
                            reason=None,
                        ))
    
    # Parse opportunities
    opportunities = None
    if trend_analysis.opportunities:
        opps_data = trend_analysis.opportunities
        if isinstance(opps_data, dict):
            opps_list = opps_data.get("opportunities", [])
            if isinstance(opps_list, list):
                opportunities = []
                for opp_data in opps_list:
                    if isinstance(opp_data, dict):
                        opportunities.append(EditorialOpportunityDetail(
                            angle=opp_data.get("angle", ""),
                            potential=opp_data.get("potential", "Moyen"),
                            differentiation=opp_data.get("differentiation"),
                            effort=opp_data.get("effort"),
                        ))
                    elif isinstance(opp_data, str):
                        opportunities.append(EditorialOpportunityDetail(
                            angle=opp_data,
                            potential="Élevé",
                            differentiation=None,
                            effort=None,
                        ))
    
    return TrendAnalysisDetail(
        topic_id=_slugify_topic_id(cluster.topic_id, cluster.label),
        topic_title=cluster.label,
        synthesis=trend_analysis.synthesis,
        saturated_angles=saturated_angles,
        opportunities=opportunities,
        llm_model=trend_analysis.llm_model_used,
        generated_at=trend_analysis.created_at,
    )


async def _get_trend_analyses(
    db: AsyncSession,
    trend_execution: Optional[Any],
) -> List[TrendAnalysisDetail]:
    """
    Get all trend analyses with opportunities and saturated angles.
    
    Args:
        db: Database session
        trend_execution: TrendPipelineExecution (optional)
        
    Returns:
        List of TrendAnalysisDetail
    """
    if not trend_execution:
        return []
    
    from python_scripts.database.crud_llm_results import get_trend_analyses_by_analysis
    
    # Get all trend analyses for this execution
    trend_analyses = await get_trend_analyses_by_analysis(db, trend_execution.id)
    
    if not trend_analyses:
        return []
    
    # Format each analysis
    analyses_list = []
    for trend_analysis in trend_analyses:
        # Get the cluster
        cluster_stmt = select(TopicCluster).where(
            TopicCluster.id == trend_analysis.topic_cluster_id,
            TopicCluster.is_valid == True,  # noqa: E712
        )
        cluster_result = await db.execute(cluster_stmt)
        cluster = cluster_result.scalar_one_or_none()
        
        if cluster:
            analysis_detail = await _format_trend_analysis(db, trend_analysis, cluster)
            analyses_list.append(analysis_detail)
    
    return analyses_list


async def _get_temporal_insights(
    db: AsyncSession,
    trend_execution: Optional[Any],
) -> List[TemporalInsight]:
    """
    Get temporal insights grouped by topic.
    
    Args:
        db: Database session
        trend_execution: TrendPipelineExecution (optional)
        
    Returns:
        List of TemporalInsight
    """
    if not trend_execution:
        return []
    
    from python_scripts.api.schemas.responses import TimeWindow
    
    # Get all clusters
    clusters = await get_topic_clusters_by_analysis(
        db,
        trend_execution.id,
        scope=None,
        only_valid=True,
    )
    
    if not clusters:
        return []
    
    insights_list = []
    
    for cluster in clusters:
        # Get temporal metrics for this cluster
        temporal_metrics = await get_temporal_metrics_by_topic_cluster(db, cluster.id)
        
        if not temporal_metrics:
            continue
        
        # Build time windows
        time_windows = []
        for metric in temporal_metrics[:3]:  # Limit to 3 most recent windows
            # Determine period label
            period = "30 derniers jours"  # Default
            if metric.window_start and metric.window_end:
                days_diff = (metric.window_end - metric.window_start).days
                if days_diff <= 7:
                    period = "7 derniers jours"
                elif days_diff <= 14:
                    period = "14 derniers jours"
                elif days_diff <= 30:
                    period = "30 derniers jours"
                else:
                    period = f"{days_diff} derniers jours"
            
            # Determine trend direction
            trend_direction = None
            if metric.velocity:
                trend_direction = _determine_trend(float(metric.velocity))
            
            time_windows.append(TimeWindow(
                period=period,
                volume=metric.volume,
                velocity=float(metric.velocity) if metric.velocity else None,
                freshness_ratio=float(metric.freshness_ratio) if metric.freshness_ratio else None,
                trend_direction=trend_direction,
                drift_detected=metric.drift_detected,
            ))
        
        if time_windows:
            latest_metric = temporal_metrics[0]
            insight = TemporalInsight(
                topic_id=_slugify_topic_id(cluster.topic_id, cluster.label),
                topic_title=cluster.label,
                time_windows=time_windows,
                cohesion_score=float(latest_metric.cohesion_score) if latest_metric.cohesion_score else None,
                potential_score=float(latest_metric.potential_score) if latest_metric.potential_score else None,
                source_diversity=latest_metric.source_diversity,
            )
            insights_list.append(insight)
    
    return insights_list


async def _format_editorial_opportunity(
    db: AsyncSession,
    article_reco: ArticleRecommendation,
    profile: SiteProfile,
) -> EditorialOpportunity:
    """
    Format an ArticleRecommendation into EditorialOpportunity.
    
    Args:
        db: Database session
        article_reco: ArticleRecommendation instance
        profile: SiteProfile instance
        
    Returns:
        EditorialOpportunity
    """
    # Get the cluster
    cluster_stmt = select(TopicCluster).where(
        TopicCluster.id == article_reco.topic_cluster_id,
        TopicCluster.is_valid == True,  # noqa: E712
    )
    cluster_result = await db.execute(cluster_stmt)
    cluster = cluster_result.scalar_one_or_none()
    
    if not cluster:
        # Return a minimal opportunity if cluster not found
        return EditorialOpportunity(
            id=article_reco.id,
            topic_id="unknown",
            topic_title="Unknown Topic",
            article_title=article_reco.title,
            hook=article_reco.hook,
            effort_level=article_reco.effort_level,
            effort_label="Effort moyen",
            differentiation_score=float(article_reco.differentiation_score) if article_reco.differentiation_score else None,
            differentiation_label=None,
            status=article_reco.status,
            status_label="Suggéré",
            outline=article_reco.outline if isinstance(article_reco.outline, dict) else None,
            related_domain=None,
            created_at=article_reco.created_at,
        )
    
    # Map effort level to label
    effort_labels = {
        "easy": "Effort faible",
        "medium": "Effort moyen",
        "complex": "Effort élevé",
    }
    effort_label = effort_labels.get(article_reco.effort_level, "Effort moyen")
    
    # Map status to label
    status_labels = {
        "suggested": "Suggéré",
        "approved": "Approuvé",
        "in_progress": "En cours",
        "published": "Publié",
    }
    status_label = status_labels.get(article_reco.status, "Suggéré")
    
    # Map differentiation score to label
    differentiation_label = None
    if article_reco.differentiation_score:
        score = float(article_reco.differentiation_score)
        if score >= 80:
            differentiation_label = "Très différenciant"
        elif score >= 60:
            differentiation_label = "Différenciant"
        elif score >= 40:
            differentiation_label = "Moyennement différenciant"
        else:
            differentiation_label = "Peu différenciant"
    
    # Find related domain
    related_domain = None
    activity_domains = _safe_json_field(profile.activity_domains) or {}
    primary_domains = activity_domains.get("primary_domains", [])
    
    # Get articles for this topic
    articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.topic_id == cluster.topic_id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
        .limit(10)
    )
    articles_result = await db.execute(articles_stmt)
    articles = list(articles_result.scalars().all())
    
    # Find domain with most matching articles
    domain_counts = {}
    for domain in primary_domains:
        count = _count_articles_for_domain(articles, domain)
        if count > 0:
            domain_counts[domain] = count
    
    if domain_counts:
        related_domain = max(domain_counts.items(), key=lambda x: x[1])[0]
    
    return EditorialOpportunity(
        id=article_reco.id,
        topic_id=_slugify_topic_id(cluster.topic_id, cluster.label),
        topic_title=cluster.label,
        article_title=article_reco.title,
        hook=article_reco.hook,
        effort_level=article_reco.effort_level,
        effort_label=effort_label,
        differentiation_score=float(article_reco.differentiation_score) if article_reco.differentiation_score else None,
        differentiation_label=differentiation_label,
        status=article_reco.status,
        status_label=status_label,
        outline=article_reco.outline if isinstance(article_reco.outline, dict) else None,
        related_domain=related_domain,
        created_at=article_reco.created_at,
    )


async def _get_editorial_opportunities(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any],
) -> List[EditorialOpportunity]:
    """
    Get editorial opportunities (article recommendations).
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional)
        
    Returns:
        List of EditorialOpportunity
    """
    if not trend_execution:
        return []
    
    # Get all article recommendations for this execution
    from python_scripts.database.crud_llm_results import get_article_recommendations_by_analysis
    
    article_recos = await get_article_recommendations_by_analysis(db, trend_execution.id)
    
    # Filter by status (suggested or approved)
    filtered_recos = [
        reco for reco in article_recos
        if reco.status in ["suggested", "approved"] and reco.is_valid
    ]
    
    # Format each recommendation
    opportunities = []
    for reco in filtered_recos:
        opportunity = await _format_editorial_opportunity(db, reco, profile)
        if opportunity:
            opportunities.append(opportunity)
    
    # Sort by differentiation_score (descending), then by created_at
    opportunities.sort(
        key=lambda o: (
            -(o.differentiation_score or 0),
            o.created_at,
        )
    )
    
    return opportunities


def _generate_domain_summary(
    articles: List[Any], domain_label: str, keywords: Optional[Dict[str, Any]]
) -> str:
    """
    Generate domain summary from articles and keywords.
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label
        keywords: Keywords dictionary from site profile
        
    Returns:
        Summary string
    """
    # Try to extract keywords from articles matching this domain
    matching_articles = []
    domain_keywords = set(domain_label.lower().split())
    
    for article in articles[:20]:  # Limit to first 20 for performance
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            matching_articles.append(article)
    
    # Extract keywords from matching articles
    extracted_keywords = []
    for article in matching_articles[:5]:  # Limit to 5 articles
        if hasattr(article, "keywords") and article.keywords:
            article_keywords = article.keywords
            if isinstance(article_keywords, dict):
                primary = article_keywords.get("primary_keywords", [])
                if isinstance(primary, list):
                    extracted_keywords.extend(primary[:3])  # Top 3 per article
    
    # Fallback to site profile keywords
    if not extracted_keywords and keywords:
        if isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            if isinstance(primary_keywords, list):
                extracted_keywords = primary_keywords[:5]
    
    # Build summary
    if extracted_keywords:
        # Take unique keywords and join
        unique_keywords = list(dict.fromkeys(extracted_keywords))[:5]
        summary = ", ".join(str(k) for k in unique_keywords)
        return f"{summary}"
    else:
        # Fallback to domain label with generic description
        return f"{domain_label}, services et solutions"


def _generate_domain_summary_persistent(
    articles: List[Any], domain_label: str, keywords: Optional[Dict[str, Any]]
) -> str:
    """
    Generate personalized domain summary from articles matching the domain.
    
    Implements the complete algorithm from issue #002:
    1. Filter articles matching the domain (title, keywords, content)
    2. Extract terms from titles and keywords
    3. Count frequency and select top terms
    4. Generate summary from most frequent terms
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label (e.g., "Cloud Computing")
        keywords: Keywords dictionary from site profile (fallback)
        
    Returns:
        Personalized summary string
    """
    import re
    from collections import Counter
    
    # Step 1: Extract domain keywords and add synonyms
    domain_keywords = set(domain_label.lower().split())
    # Remove common words
    domain_keywords = {kw for kw in domain_keywords if len(kw) > 3}
    
    # Add common synonyms/variations (basic implementation)
    domain_variations = set(domain_keywords)
    for kw in domain_keywords:
        # Add plural/singular variations
        if kw.endswith("s"):
            domain_variations.add(kw[:-1])
        else:
            domain_variations.add(f"{kw}s")
    
    # Step 2: Filter articles matching the domain
    matching_articles = []
    for article in articles[:1000]:  # Limit to 1000 for performance
        matches = False
        
        # Check title (at least 2 keywords)
        if hasattr(article, "title") and article.title:
            title_lower = article.title.lower()
            matching_keywords = sum(1 for kw in domain_variations if kw in title_lower)
            if matching_keywords >= 2:
                matches = True
        
        # Check article keywords
        if not matches and hasattr(article, "keywords") and article.keywords:
            article_keywords = article.keywords
            if isinstance(article_keywords, dict):
                primary = article_keywords.get("primary_keywords", [])
                if isinstance(primary, list):
                    keywords_str = " ".join(str(k).lower() for k in primary)
                    if any(kw in keywords_str for kw in domain_variations):
                        matches = True
        
        # Check content (first 500 characters)
        if not matches and hasattr(article, "content_text") and article.content_text:
            content_preview = article.content_text[:500].lower()
            if any(kw in content_preview for kw in domain_variations):
                matches = True
        
        if matches:
            matching_articles.append(article)
    
    # If not enough matching articles, use fallback
    if len(matching_articles) < 3:
        return _generate_domain_summary(articles, domain_label, keywords)
    
    # Step 3: Extract terms from matching articles
    all_terms = []
    
    # Extract from titles
    stop_words = {"le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "pour", "avec", "sans", "dans", "sur"}
    for article in matching_articles[:500]:  # Limit to 500 articles
        if hasattr(article, "title") and article.title:
            # Extract words > 4 characters, not stop words
            words = re.findall(r"\b\w{5,}\b", article.title.lower())
            words = [w for w in words if w not in stop_words and w not in domain_keywords]
            all_terms.extend(words)
        
        # Extract from article keywords
        if hasattr(article, "keywords") and article.keywords:
            article_keywords = article.keywords
            if isinstance(article_keywords, dict):
                primary = article_keywords.get("primary_keywords", [])
                if isinstance(primary, list):
                    # Filter out domain keywords
                    filtered = [
                        str(k).lower() for k in primary
                        if len(str(k)) > 4 and str(k).lower() not in domain_keywords
                    ]
                    all_terms.extend(filtered)
    
    # Step 4: Count frequency and select top terms
    if not all_terms:
        # Fallback to site profile keywords
        if keywords and isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            if isinstance(primary_keywords, list):
                all_terms = [str(k).lower() for k in primary_keywords[:10]]
    
    if not all_terms:
        return f"{domain_label}, services et solutions"
    
    # Count frequency
    term_counts = Counter(all_terms)
    
    # Get top 3-5 terms (excluding domain keywords)
    top_terms = [
        term for term, count in term_counts.most_common(10)
        if term not in domain_keywords
    ][:5]
    
    # Build summary
    if top_terms:
        summary = ", ".join(top_terms)
        return summary
    else:
        # Fallback
        return _generate_domain_summary(articles, domain_label, keywords)


async def _save_domain_summaries_to_profile(
    db: AsyncSession,
    profile: SiteProfile,
    trend_execution: Optional[Any] = None,
) -> None:
    """
    Generate and save personalized domain summaries to activity_domains.domain_details.
    
    Implements issue #002: stores summaries in activity_domains.domain_details JSONB structure.
    
    Args:
        db: Database session
        profile: SiteProfile instance
        trend_execution: TrendPipelineExecution (optional, for topics_count)
    """
    from python_scripts.database.crud_client_articles import list_client_articles
    from datetime import datetime, timezone
    
    # Get activity domains
    activity_domains = _safe_json_field(profile.activity_domains) or {}
    primary_domains = activity_domains.get("primary_domains", [])
    secondary_domains = activity_domains.get("secondary_domains", [])
    all_domains = primary_domains + secondary_domains
    
    if not all_domains:
        logger.warning("No activity domains found for profile", domain=profile.domain)
        return
    
    # Get all client articles
    client_articles = await list_client_articles(
        db, site_profile_id=profile.id, limit=1000
    )
    
    # Initialize domain_details if not exists
    domain_details = activity_domains.get("domain_details", {})
    if not isinstance(domain_details, dict):
        domain_details = {}
    
    # Generate summary for each domain
    for domain_label in all_domains:
        domain_slug = _slugify(domain_label)
        
        # Count articles for this domain
        articles_count = _count_articles_for_domain(client_articles, domain_label)
        total_articles = len(client_articles)
        confidence = min(100, int((articles_count / total_articles) * 100)) if total_articles > 0 else 0
        
        # Count topics if trend_execution available
        topics_count = 0
        if trend_execution:
            topics_count = await _count_topics_for_domain(
                db, profile, trend_execution, domain_label
            )
        
        # Generate personalized summary
        summary = _generate_domain_summary_persistent(
            client_articles,
            domain_label,
            _safe_json_field(profile.keywords),
        )
        
        # Update domain_details
        domain_details[domain_slug] = {
            "label": domain_label,
            "summary": summary,
            "topics_count": topics_count,
            "confidence": confidence,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "source_articles_count": articles_count,
        }
    
    # Update activity_domains with domain_details
    activity_domains["domain_details"] = domain_details
    
    # Save to database
    await update_site_profile(
        db,
        profile,
        activity_domains=activity_domains,
    )
    
    logger.info(
        "Domain summaries saved to profile",
        domain=profile.domain,
        domains_count=len(all_domains),
    )


def _calculate_read_time(word_count: int) -> str:
    """
    Calculate estimated read time from word count.
    
    Args:
        word_count: Number of words
        
    Returns:
        Read time string (e.g., "8 min")
    """
    # Average reading speed: 200 words per minute
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min"


def _determine_trend(velocity: Optional[float]) -> Optional[str]:
    """
    Determine trend direction from velocity.
    
    Args:
        velocity: Velocity metric from temporal analysis
        
    Returns:
        Trend direction: "up", "stable", or "down"
    """
    if velocity is None:
        return None
    
    if velocity > 0.1:
        return "up"
    elif velocity < -0.1:
        return "down"
    else:
        return "stable"


def _slugify_topic_id(topic_id: int, label: str) -> str:
    """
    Generate a slug identifier for a topic.
    
    Args:
        topic_id: Topic ID
        label: Topic label
        
    Returns:
        Slug identifier
    """
    slug = _slugify(label)
    return f"{slug}-{topic_id}" if slug else f"topic-{topic_id}"


def _extract_topic_id_from_slug(slug: str) -> Optional[int]:
    """
    Extract topic_id from slug format: "label-topic_id" or "label-topic_id-extra".
    
    Args:
        slug: Topic slug (e.g., "edge-cloud-hybride-5" or "erpnext_erp_votre-11")
        
    Returns:
        Topic ID if found, None otherwise
    """
    # Parse slug to extract topic_id
    # Format: {label}-{topic_id} or {label}-{topic_id}-{extra}
    parts = slug.split("-")
    # Try to find numeric part at the end
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


async def _get_cluster_by_topic_id(
    db: AsyncSession,
    trend_execution_id: int,
    topic_id: int,
) -> Optional[TopicCluster]:
    """
    Get topic cluster by topic_id.
    
    Args:
        db: Database session
        trend_execution_id: Trend pipeline execution ID
        topic_id: Topic ID
        
    Returns:
        TopicCluster if found, None otherwise
    """
    from python_scripts.database.crud_clusters import get_topic_cluster_by_topic_id
    
    return await get_topic_cluster_by_topic_id(
        db, trend_execution_id, topic_id
    )


def _extract_key_points_from_outline(outline: Dict[str, Any]) -> List[str]:
    """
    Extract key points from article recommendation outline.
    
    Args:
        outline: Outline dictionary from ArticleRecommendation
        
    Returns:
        List of key points
    """
    key_points = []
    
    if isinstance(outline, dict):
        # Extract from sections
        for section_key, section_data in outline.items():
            if isinstance(section_data, dict):
                # Get section title
                if "title" in section_data:
                    key_points.append(section_data["title"])
                
                # Get key_points from section
                if "key_points" in section_data:
                    points = section_data["key_points"]
                    if isinstance(points, list):
                        key_points.extend(points)
    
    return key_points[:10]  # Limit to 10 points


def _transform_opportunities_to_angles(
    opportunities: Optional[List[str]],
    article_recommendations: List[Any],
) -> List[Any]:
    """
    Transform opportunities and article recommendations into angle details.
    
    Args:
        opportunities: List of opportunity strings from TrendAnalysis
        article_recommendations: List of ArticleRecommendation
        
    Returns:
        List of AngleDetail
    """
    from python_scripts.api.schemas.responses import AngleDetail
    
    angles = []
    
    # Use article recommendations if available
    for reco in article_recommendations[:3]:  # Limit to 3
        potential = "Élevé"
        if reco.differentiation_score:
            if reco.differentiation_score >= 0.7:
                potential = "Très élevé"
            elif reco.differentiation_score < 0.4:
                potential = "Moyen"
        
        differentiation = None
        if reco.differentiation_score:
            differentiation = f"Score de différenciation: {reco.differentiation_score:.2f}"
        
        angles.append(AngleDetail(
            angle=reco.title,
            description=reco.hook,
            differentiation=differentiation,
            potential=potential,
        ))
    
    # Fallback to opportunities if no recommendations
    if not angles and opportunities:
        for opp in opportunities[:3]:  # Limit to 3
            angles.append(AngleDetail(
                angle=opp,
                description=f"Opportunité éditoriale: {opp}",
                differentiation=None,
                potential="Élevé",
            ))
    
    return angles


def _calculate_trend_delta(
    current_velocity: Optional[float],
    previous_velocity: Optional[float],
) -> Optional[str]:
    """
    Calculate trend delta description.
    
    Args:
        current_velocity: Current velocity value
        previous_velocity: Previous velocity value (optional)
        
    Returns:
        Delta description string or None
    """
    if current_velocity is None:
        return None
    
    if previous_velocity is not None and previous_velocity > 0:
        delta_pct = ((current_velocity - previous_velocity) / previous_velocity) * 100
        return f"{delta_pct:+.1f}% de recherches sur ce sujet dans les 30 derniers jours"
    
    # Fallback: estimate from velocity
    if current_velocity > 1.2:
        return "+35% de recherches sur ce sujet dans les 30 derniers jours"
    elif current_velocity > 0.8:
        return "Stable"
    else:
        return "-20% de recherches sur ce sujet dans les 30 derniers jours"


def _generate_predictions(
    volume: int,
    effort_level: Optional[str],
    differentiation_score: Optional[float],
) -> Any:
    """
    Generate predictions based on metrics.
    
    Args:
        volume: Article volume
        effort_level: Effort level from ArticleRecommendation
        differentiation_score: Differentiation score
        
    Returns:
        TopicPredictions
    """
    from python_scripts.api.schemas.responses import TopicPredictions
    
    # Estimate views based on volume
    if volume > 100:
        views_range = "2,500 - 4,000"
    elif volume > 50:
        views_range = "1,500 - 2,500"
    else:
        views_range = "500 - 1,500"
    
    # Estimate shares (roughly 2-3% of views)
    shares_range = "50 - 80"
    
    # Estimate writing time from effort level
    writing_time = "2-3 heures"
    if effort_level == "easy":
        writing_time = "1-2 heures"
    elif effort_level == "complex":
        writing_time = "4-6 heures"
    
    # Difficulty from effort level
    difficulty = "Intermédiaire"
    if effort_level == "easy":
        difficulty = "Facile"
    elif effort_level == "complex":
        difficulty = "Avancé"
    
    return TopicPredictions(
        views=views_range,
        shares=shares_range,
        writing_time=writing_time,
        difficulty=difficulty,
    )


async def _check_site_profile(
    db: AsyncSession, domain: str
) -> Optional[SiteProfile]:
    """
    Check if site profile exists for domain.
    
    Args:
        db: Database session
        domain: Domain name
        
    Returns:
        SiteProfile if exists, None otherwise
    """
    return await get_site_profile_by_domain(db, domain)


async def _check_competitors(
    db: AsyncSession, domain: str
) -> Optional[Any]:
    """
    Check if competitor search exists and is completed.
    
    Args:
        db: Database session
        domain: Domain name
        
    Returns:
        WorkflowExecution if exists and completed, None otherwise
    """
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "competitor_search",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
        )
        .order_by(desc(WorkflowExecution.start_time))
        .limit(1)
    )
    
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    
    if execution and execution.output_data:
        competitors_data = execution.output_data.get("competitors", [])
        if competitors_data:
            return execution
    
    return None


async def _check_competitor_articles(
    db: AsyncSession, competitor_domains: List[str], client_domain: Optional[str] = None
) -> tuple[int, bool]:
    """
    Count competitor articles and check if sufficient in both PostgreSQL AND Qdrant.

    This function ensures consistency between PostgreSQL and Qdrant by checking:
    1. Number of articles in PostgreSQL
    2. Number of articles indexed in Qdrant collection

    If Qdrant collection is empty or has fewer articles than PostgreSQL,
    returns is_sufficient=False to trigger re-scraping/re-indexing.

    Args:
        db: Database session
        competitor_domains: List of competitor domains
        client_domain: Client domain for generating Qdrant collection name

    Returns:
        Tuple of (count, is_sufficient) where is_sufficient is True if:
        - PostgreSQL has >= 10 articles AND
        - Qdrant has >= 10 articles (ensuring consistency)
    """
    from python_scripts.database.crud_articles import count_competitor_articles
    from python_scripts.vectorstore.qdrant_client import qdrant_client, get_competitor_collection_name

    if not competitor_domains:
        return (0, False)

    # Count articles in PostgreSQL
    postgres_count = 0
    for comp_domain in competitor_domains:
        count = await count_competitor_articles(db, domain=comp_domain)
        postgres_count += count

    # Check Qdrant collection if client_domain is provided
    qdrant_count = 0
    if client_domain:
        try:
            collection_name = get_competitor_collection_name(client_domain)

            # Check if collection exists and get count
            if qdrant_client.collection_exists(collection_name):
                collection_info = qdrant_client.client.get_collection(collection_name)
                qdrant_count = getattr(collection_info, "points_count", 0)

                logger.info(
                    "Competitor articles count check",
                    postgres_count=postgres_count,
                    qdrant_count=qdrant_count,
                    collection=collection_name,
                    domains_count=len(competitor_domains),
                )

                # If mismatch detected, log warning
                if postgres_count > 0 and qdrant_count == 0:
                    logger.warning(
                        "Inconsistency detected: PostgreSQL has articles but Qdrant is empty",
                        postgres_count=postgres_count,
                        qdrant_count=0,
                        collection=collection_name,
                        recommendation="Will trigger re-scraping to re-index articles in Qdrant",
                    )
                elif abs(postgres_count - qdrant_count) > postgres_count * 0.2:  # >20% difference
                    logger.warning(
                        "Inconsistency detected: PostgreSQL and Qdrant counts differ significantly",
                        postgres_count=postgres_count,
                        qdrant_count=qdrant_count,
                        difference=abs(postgres_count - qdrant_count),
                        collection=collection_name,
                    )
            else:
                logger.info(
                    "Qdrant collection does not exist",
                    collection=collection_name,
                    postgres_count=postgres_count,
                )
        except Exception as e:
            logger.warning(
                "Could not check Qdrant collection",
                error=str(e),
                client_domain=client_domain,
            )
            # If we can't check Qdrant, assume it needs re-indexing
            qdrant_count = 0
    else:
        # No client_domain provided, only check PostgreSQL
        logger.info(
            "No client_domain provided, checking PostgreSQL only",
            postgres_count=postgres_count,
        )
        qdrant_count = postgres_count  # Assume Qdrant is in sync

    # Consider sufficient only if BOTH PostgreSQL AND Qdrant have enough articles
    # This ensures consistency between the two systems
    import os
    min_required = int(os.getenv("MIN_COMPETITOR_ARTICLES_FOR_AUDIT", "10"))
    is_sufficient = postgres_count >= min_required and qdrant_count >= min_required

    return (postgres_count, is_sufficient)


async def _check_client_articles(
    db: AsyncSession, site_profile_id: int
) -> tuple[int, bool]:
    """
    Count client articles and check if sufficient.
    
    Args:
        db: Database session
        site_profile_id: Site profile ID
        
    Returns:
        Tuple of (count, is_sufficient) where is_sufficient is True if count >= MIN_CLIENT_ARTICLES_FOR_AUDIT (default: 5)
    """
    from python_scripts.database.crud_client_articles import count_client_articles
    
    count = await count_client_articles(db, site_profile_id=site_profile_id)
    import os
    min_required = int(os.getenv("MIN_CLIENT_ARTICLES_FOR_AUDIT", "5"))
    return (count, count >= min_required)


async def _check_trend_pipeline(
    db: AsyncSession, domain: str
) -> Optional[Any]:
    """
    Check if trend pipeline exists and is completed.
    
    Args:
        db: Database session
        domain: Client domain name
        
    Returns:
        TrendPipelineExecution if exists and all stages completed, None otherwise
    """
    from sqlalchemy import select, desc
    from python_scripts.database.models import TrendPipelineExecution
    
    stmt = (
        select(TrendPipelineExecution)
        .where(
            TrendPipelineExecution.client_domain == domain,
            TrendPipelineExecution.stage_1_clustering_status == "completed",
            TrendPipelineExecution.stage_2_temporal_status == "completed",
            TrendPipelineExecution.stage_3_llm_status == "completed",
        )
        .order_by(desc(TrendPipelineExecution.start_time))
        .limit(1)
    )
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def build_complete_audit_from_database(
    db: AsyncSession,
    domain: str,
    profile: SiteProfile,
    competitors_execution: Optional[Any],
    trend_execution: Optional[Any],
    include_topics: bool = False,
    include_trending: bool = True,
    include_analyses: bool = True,
    include_temporal: bool = True,
    include_opportunities: bool = True,
    topics_limit: int = 10,
    trending_limit: int = 15,
) -> SiteAuditResponse:
    """
    Build complete audit response from database data.
    
    All data is assumed to exist.
    
    Args:
        db: Database session
        domain: Domain name
        profile: SiteProfile instance
        competitors_execution: WorkflowExecution for competitors (optional)
        trend_execution: TrendPipelineExecution (optional)
        
    Returns:
        Complete SiteAuditResponse
    """
    from python_scripts.database.crud_client_articles import list_client_articles
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    # 1. URL
    url = f"https://{domain}"
    
    # 2. Profile.style
    style = {
        "tone": profile.editorial_tone or "professionnel",
        "vocabulary": _map_language_level_to_vocabulary(profile.language_level),
        "format": _calculate_article_format(_safe_json_field(profile.content_structure)),
    }
    
    # 3. Profile.themes
    activity_domains = _safe_json_field(profile.activity_domains) or {}
    themes = activity_domains.get("primary_domains", [])
    
    # 4. Domains (domaines d'activité détaillés)
    domains_list = []
    
    # Récupérer les articles client pour calculer confidence et summary
    client_articles = await list_client_articles(
        db, site_profile_id=profile.id, limit=1000
    )
    
    # S'assurer que themes est une liste (peut être None ou vide)
    if not themes:
        themes = []
    
    # Pour chaque domaine d'activité
    for domain_label in themes:
        # Calculer topics_count (nombre de clusters/topics pertinents du trend pipeline)
        topics_count = await _count_topics_for_domain(
            db, profile, trend_execution, domain_label
        )
        
        # Calculer confidence (basé sur le nombre d'articles client correspondants)
        # Garder cette logique pour confidence car elle reflète la couverture du site client
        articles_count = _count_articles_for_domain(client_articles, domain_label)
        total_articles = len(client_articles)
        if total_articles > 0:
            confidence = min(100, int((articles_count / total_articles) * 100))
        else:
            confidence = 0
        
        # Try to read summary from domain_details (issue #002)
        domain_slug = _slugify(domain_label)
        activity_domains_data = _safe_json_field(profile.activity_domains) or {}
        domain_details = activity_domains_data.get("domain_details", {})
        
        summary = None
        if isinstance(domain_details, dict) and domain_slug in domain_details:
            domain_detail = domain_details[domain_slug]
            if isinstance(domain_detail, dict):
                summary = domain_detail.get("summary")
        
        # Fallback: generate on the fly if not in domain_details
        if not summary:
            summary = _generate_domain_summary_persistent(
                client_articles, domain_label, _safe_json_field(profile.keywords)
            )
        
        # Always get topics and metrics to enrich the response (structure always present)
        topics = []
        metrics = None
        
        if trend_execution:
            # Always calculate metrics (lightweight operation)
            metrics = await _get_domain_metrics(
                db, profile, trend_execution, domain_label, client_articles
            )
            
            # Get topics list if requested (can be heavy, so optional)
            if include_topics:
                topics = await _get_topics_for_domain(
                    db, profile, trend_execution, domain_label, limit=topics_limit
                )
        else:
            # If no trend_execution, still provide metrics structure with article count
            # articles_count is already calculated above (line ~1966)
            metrics = DomainMetrics(
                total_articles=articles_count,
                trending_topics=0,
                avg_relevance=0.0,
                top_keywords=[],
            )
        
        # Ensure metrics is never None (fallback if something went wrong)
        if metrics is None:
            metrics = DomainMetrics(
                total_articles=articles_count,
                trending_topics=0,
                avg_relevance=0.0,
                top_keywords=[],
            )
        
        domains_list.append(
            DomainDetail(
                id=_slugify(domain_label),
                label=domain_label,
                confidence=confidence,
                topics_count=topics_count,  # Maintenant = nombre de clusters pertinents
                summary=summary,
                topics=topics,  # Always a list (empty if include_topics=False)
                metrics=metrics,  # Always present (never None)
            )
        )
    
    # 5. Audience
    target_audience = _safe_json_field(profile.target_audience) or {}
    audience = {
        "type": target_audience.get("primary", "Professionnels IT"),
        "level": _map_language_level_to_audience_level(profile.language_level),
        "sectors": _extract_audience_sectors(target_audience),
    }
    # S'assurer que sectors est toujours une liste
    if "sectors" not in audience or not isinstance(audience["sectors"], list):
        audience["sectors"] = []
    
    # 6. Competitors (top 5, triés par similarity puis alphabétique)
    competitors = []
    if competitors_execution and competitors_execution.output_data:
        competitors_data = competitors_execution.output_data.get("competitors", [])
        # Filtrer et formater les concurrents validés OU tous les concurrents si aucun n'est validé
        competitors_list = []
        validated_competitors = [
            comp for comp in competitors_data
            if comp.get("validated", False) or comp.get("manual", False)
        ]
        
        # Si aucun concurrent validé, utiliser tous les concurrents non exclus
        competitors_to_use = validated_competitors if validated_competitors else [
            comp for comp in competitors_data
            if comp.get("domain") and not comp.get("excluded", False)
        ]
        
        for comp in competitors_to_use:
            relevance = comp.get("relevance_score", 0.0)
            domain_name = comp.get("domain", "")
            if domain_name:  # Ignorer les domaines vides
                competitors_list.append({
                    "name": domain_name,
                    "similarity": int(relevance * 100),
                })
        
        # Trier : d'abord par similarity (décroissant), puis par nom (alphabétique)
        competitors_list.sort(key=lambda x: (-x["similarity"], x["name"]))
        
        # Prendre les 5 meilleurs
        competitors = competitors_list[:5]
    
    # S'assurer que competitors est toujours une liste (pas None)
    if competitors is None:
        competitors = []
    
    # 7. took_ms (durée de la dernière analyse)
    took_ms = 0
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "editorial_analysis",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
        )
        .order_by(desc(WorkflowExecution.start_time))
        .limit(1)
    )
    result = await db.execute(stmt)
    last_execution = result.scalar_one_or_none()
    
    if last_execution and last_execution.duration_seconds:
        took_ms = last_execution.duration_seconds * 1000
    
    # 8. Build new sections if trend_execution exists
    trending_topics_section = None
    trend_analyses_section = None
    temporal_insights_section = None
    editorial_opportunities_section = None
    
    if trend_execution:
        if include_trending:
            trending_topics = await _get_trending_topics(
                db, profile, trend_execution, limit=trending_limit
            )
            if trending_topics:
                trending_topics_section = TrendingTopicsSection(
                    topics=trending_topics,
                    summary={
                        "total_trending": len(trending_topics),
                        "avg_growth": round(
                            sum(t.growth_rate for t in trending_topics) / len(trending_topics), 1
                        ) if trending_topics else 0.0,
                        "high_potential_count": sum(
                            1 for t in trending_topics if t.potential_score and t.potential_score > 80
                        ),
                    },
                )
        
        if include_analyses:
            trend_analyses = await _get_trend_analyses(db, trend_execution)
            if trend_analyses:
                trend_analyses_section = TrendAnalysesSection(
                    analyses=trend_analyses,
                    summary={
                        "total_analyses": len(trend_analyses),
                        "high_potential_opportunities": sum(
                            1 for a in trend_analyses
                            if a.opportunities and len(a.opportunities) > 0
                        ),
                        "saturated_angles_count": sum(
                            1 for a in trend_analyses
                            if a.saturated_angles and len(a.saturated_angles) > 0
                        ),
                    },
                )
        
        if include_temporal:
            temporal_insights = await _get_temporal_insights(db, trend_execution)
            if temporal_insights:
                temporal_insights_section = TemporalInsightsSection(
                    insights=temporal_insights,
                    summary={
                        "fastest_growing": sum(
                            1 for i in temporal_insights
                            if i.time_windows
                            and i.time_windows[0].trend_direction == "up"
                        ),
                        "most_fresh": sum(
                            1 for i in temporal_insights
                            if i.time_windows
                            and i.time_windows[0].freshness_ratio
                            and i.time_windows[0].freshness_ratio > 0.7
                        ),
                        "highest_potential": sum(
                            1 for i in temporal_insights
                            if i.potential_score and i.potential_score > 80
                        ),
                    },
                )
        
        if include_opportunities:
            editorial_opportunities = await _get_editorial_opportunities(
                db, profile, trend_execution
            )
            if editorial_opportunities:
                # Count by effort level
                by_effort = {"easy": 0, "medium": 0, "complex": 0}
                for opp in editorial_opportunities:
                    if opp.effort_level in by_effort:
                        by_effort[opp.effort_level] += 1
                
                # Count by status
                by_status = {"suggested": 0, "approved": 0, "in_progress": 0, "published": 0}
                for opp in editorial_opportunities:
                    if opp.status in by_status:
                        by_status[opp.status] += 1
                
                editorial_opportunities_section = EditorialOpportunitiesSection(
                    recommendations=editorial_opportunities,
                    summary={
                        "total_recommendations": len(editorial_opportunities),
                        "by_effort": by_effort,
                        "by_status": by_status,
                        "high_differentiation": sum(
                            1 for opp in editorial_opportunities
                            if opp.differentiation_score and opp.differentiation_score >= 80
                        ),
                    },
                )
    
    return SiteAuditResponse(
        url=url,
        profile={
            "style": style,
            "themes": themes,
        },
        domains=domains_list,
        audience=audience,
        competitors=competitors,
        took_ms=took_ms,
        trending_topics=trending_topics_section,
        trend_analyses=trend_analyses_section,
        temporal_insights=temporal_insights_section,
        editorial_opportunities=editorial_opportunities_section,
    )


def _normalize_site_client(site_client: str) -> str:
    """
    Normalize site_client parameter to extract domain from URL if needed.
    
    Handles cases like:
    - "https://innosys.fr" -> "innosys.fr"
    - "http://innosys.fr" -> "innosys.fr"
    - "www.innosys.fr" -> "innosys.fr"
    - "innosys.fr" -> "innosys.fr"
    - "innosys" -> "innosys"
    
    Args:
        site_client: Client site identifier (can be URL, domain, or name)
        
    Returns:
        Normalized domain string
    """
    from urllib.parse import urlparse
    
    # If it looks like a URL, extract the domain
    if site_client.startswith(("http://", "https://")):
        try:
            parsed = urlparse(site_client)
            domain = parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            domain = site_client
    else:
        domain = site_client
    
    # Remove www. prefix if present
    if domain.startswith("www."):
        domain = domain[4:]
    
    # Remove trailing slash if present
    domain = domain.rstrip("/")
    
    return domain.lower() if domain else site_client


async def _get_topics_by_domain(
    db: AsyncSession,
    site_client: str,
    domain_topic: str,
) -> DomainTopicsResponse:
    """
    Get topics for a specific activity domain.
    
    Args:
        db: Database session
        site_client: Client site identifier (e.g., "innosys", "innosys.fr", or "https://innosys.fr")
        domain_topic: Activity domain label (e.g., "cyber")
        
    Returns:
        DomainTopicsResponse with topics list
        
    Raises:
        HTTPException: If site profile not found or no trend pipeline execution
    """
    # 1. Normalize site_client to extract domain from URL if needed
    normalized_client = _normalize_site_client(site_client)
    
    # 2. Map site_client to domain (e.g., "innosys" -> "innosys.fr")
    # Try the normalized client as-is first (in case it's already a domain like "innosys.fr")
    # Then try common patterns
    domain_candidates = [
        normalized_client,  # Try as-is first (handles "innosys.fr" case)
        f"{normalized_client}.fr",
        f"{normalized_client}.com",
    ]
    
    profile = None
    for candidate_domain in domain_candidates:
        profile = await get_site_profile_by_domain(db, candidate_domain)
        if profile:
            break
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for client: {site_client}",
        )
    
    # 2. Verify domain_topic exists in activity_domains
    activity_domains = profile.activity_domains or {}
    primary_domains = activity_domains.get("primary_domains", [])
    secondary_domains = activity_domains.get("secondary_domains", [])
    all_domains = primary_domains + secondary_domains
    
    if domain_topic not in all_domains:
        # Try to find similar domains for better error message
        domain_topic_lower = domain_topic.lower()
        similar_domains = []
        
        # Find domains that contain any of the keywords from the searched domain
        search_keywords = set(domain_topic_lower.split())
        for domain in all_domains:
            domain_lower = domain.lower()
            # Check if any keyword from search appears in the domain
            if any(keyword in domain_lower for keyword in search_keywords if len(keyword) > 3):
                similar_domains.append(domain)
        
        # Build error message
        error_detail = f"Domain topic '{domain_topic}' not found in activity domains for {profile.domain}"
        
        if similar_domains:
            error_detail += f". Similar domains found: {', '.join(similar_domains[:5])}"
        else:
            # Show first 10 available domains if no similar ones found
            available_preview = all_domains[:10]
            if len(all_domains) > 10:
                error_detail += f". Available domains (showing first 10 of {len(all_domains)}): {', '.join(available_preview)}"
            else:
                error_detail += f". Available domains: {', '.join(available_preview)}"
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail,
        )
    
    # 3. Get latest trend pipeline execution
    stmt = (
        select(TrendPipelineExecution)
        .where(
            TrendPipelineExecution.client_domain == profile.domain,
            TrendPipelineExecution.stage_1_clustering_status == "completed",
            TrendPipelineExecution.is_valid == True,  # noqa: E712
        )
        .order_by(desc(TrendPipelineExecution.start_time))
        .limit(1)
    )
    result = await db.execute(stmt)
    trend_execution = result.scalar_one_or_none()
    
    if not trend_execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed trend pipeline execution found for {profile.domain}",
        )
    
    # 4. Get topic clusters (filter by scope: core or adjacent for relevant domains)
    # Use heuristics to determine if domain is core or adjacent
    scope_filter = None  # Get all scopes, we'll filter by domain relevance later
    clusters = await get_topic_clusters_by_analysis(
        db,
        trend_execution.id,
        scope=scope_filter,
        only_valid=True,
    )
    
    if not clusters:
        logger.warning(
            "No clusters found for trend pipeline execution",
            execution_id=trend_execution.id,
            domain=profile.domain,
        )
        return DomainTopicsResponse(
            domain=domain_topic,
            count=0,
            topics=[],
        )
    
    logger.info(
        "Found clusters for trend pipeline",
        execution_id=trend_execution.id,
        total_clusters=len(clusters),
        domain_topic=domain_topic,
    )
    
    # 5. Filter clusters relevant to the domain_topic using heuristics
    # Use the same logic as /audit: check if articles in the cluster match the domain_topic
    # This is more accurate than filtering by cluster label/top_terms
    relevant_clusters = []
    
    # Get all client articles for this profile to check domain_topic matching
    all_client_articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    all_client_articles_result = await db.execute(all_client_articles_stmt)
    all_client_articles = list(all_client_articles_result.scalars().all())
    
    # Also get competitor articles (clusters are created from competitor articles)
    # We need to check both to find articles matching the domain
    all_competitor_articles_stmt = (
        select(CompetitorArticle)
        .where(
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
        .limit(5000)  # Limit for performance
    )
    all_competitor_articles_result = await db.execute(all_competitor_articles_stmt)
    all_competitor_articles = list(all_competitor_articles_result.scalars().all())
    
    # Combine all articles for domain matching
    all_articles = all_client_articles + all_competitor_articles
    
    logger.info(
        "Checking clusters against domain",
        total_client_articles=len(all_client_articles),
        total_competitor_articles=len(all_competitor_articles),
        client_articles_with_topic_id=sum(1 for art in all_client_articles if art.topic_id is not None),
        competitor_articles_with_topic_id=sum(1 for art in all_competitor_articles if art.topic_id is not None),
        domain_topic=domain_topic,
    )
    
    for cluster in clusters:
        # Get articles for this cluster
        # First try to get articles by topic_id (if assigned)
        cluster_articles_by_topic = [
            art for art in all_articles
            if art.topic_id == cluster.topic_id
        ]
        
        # If no articles found by topic_id, check if cluster document_ids match
        # This handles the case where topic_id is not yet assigned to articles
        cluster_articles = []
        if cluster_articles_by_topic:
            cluster_articles = cluster_articles_by_topic
        elif cluster.document_ids:
            # Extract document IDs from cluster (these are qdrant_point_ids as strings)
            doc_ids = cluster.document_ids.get("ids", []) or []
            if isinstance(doc_ids, list):
                # Convert all to strings for comparison (doc_ids are strings, qdrant_point_id are UUID)
                doc_ids_str = {str(doc_id).lower() for doc_id in doc_ids}
                # Find articles by qdrant_point_id (convert UUID to string for comparison)
                # Check both client and competitor articles
                cluster_articles_by_point = [
                    art for art in all_articles
                    if art.qdrant_point_id and str(art.qdrant_point_id).lower() in doc_ids_str
                ]
                cluster_articles = cluster_articles_by_point
        
        # Check if any article in this cluster matches the domain_topic
        # Use the same logic as _count_articles_for_domain
        # Filter to client articles only for domain matching (as per /audit logic)
        client_cluster_articles = [
            art for art in cluster_articles
            if isinstance(art, ClientArticle) and art.site_profile_id == profile.id
        ]
        matching_count = _count_articles_for_domain(client_cluster_articles, domain_topic)
        
        # If no client articles match, check if cluster itself is relevant to domain
        # by checking cluster label and top_terms (fallback)
        # This is important because clusters are created from competitor articles,
        # not client articles, so we need to check cluster metadata
        if matching_count == 0:
            domain_keywords = set(domain_topic.lower().split())
            # Remove common words
            domain_keywords = {kw for kw in domain_keywords if len(kw) > 3}
            
            label_lower = cluster.label.lower() if cluster.label else ""
            top_terms = cluster.top_terms.get("terms", []) if cluster.top_terms else []
            top_terms_str = " ".join(str(t).lower() for t in top_terms[:15])  # Check more terms
            
            # Check if cluster label or top_terms match domain keywords
            cluster_matches = any(
                keyword in label_lower or keyword in top_terms_str
                for keyword in domain_keywords
            )
            
            # Also check if any competitor article in the cluster matches the domain
            # This is a more accurate way to determine relevance
            if not cluster_matches and cluster_articles:
                competitor_articles = [
                    art for art in cluster_articles
                    if isinstance(art, CompetitorArticle)
                ]
                if competitor_articles:
                    competitor_matching_count = _count_articles_for_domain(competitor_articles, domain_topic)
                    if competitor_matching_count > 0:
                        cluster_matches = True
            
            if cluster_matches:
                matching_count = 1  # Consider cluster relevant even without matching client articles
        
        if matching_count > 0:
            relevant_clusters.append(cluster)
            logger.debug(
                "Cluster matches domain",
                cluster_id=cluster.id,
                topic_id=cluster.topic_id,
                label=cluster.label,
                articles_count=len(cluster_articles),
                client_articles_count=len(client_cluster_articles),
                matching_count=matching_count,
            )
    
    logger.info(
        "Filtered clusters by domain",
        total_clusters=len(clusters),
        relevant_clusters=len(relevant_clusters),
        domain_topic=domain_topic,
    )
    
    # 6. Build topic details for each relevant cluster
    topics_list = []
    
    for cluster in relevant_clusters:
        # Get trend analysis (summary)
        trend_analyses = await get_trend_analyses_by_topic_cluster(db, cluster.id)
        synthesis = trend_analyses[0].synthesis if trend_analyses else cluster.label
        
        # Get temporal metrics (for trend and relevance)
        temporal_metrics = await get_temporal_metrics_by_topic_cluster(db, cluster.id)
        latest_metric = temporal_metrics[0] if temporal_metrics else None
        
        # Calculate relevance score from coherence or volume
        relevance_score = None
        if cluster.coherence_score:
            relevance_score = int(float(cluster.coherence_score) * 100)
        elif latest_metric and latest_metric.volume:
            # Normalize volume to 0-100 (assuming max volume around 1000)
            relevance_score = min(100, int((latest_metric.volume / 10)))
        
        # Determine trend
        trend = None
        if latest_metric:
            trend = _determine_trend(float(latest_metric.velocity) if latest_metric.velocity else None)
        
        # Get articles for this topic to extract dates, sources, read_time
        articles_stmt = (
            select(ClientArticle)
            .where(
                ClientArticle.site_profile_id == profile.id,
                ClientArticle.topic_id == cluster.topic_id,
                ClientArticle.is_valid == True,  # noqa: E712
            )
        )
        client_articles_result = await db.execute(articles_stmt)
        client_articles = list(client_articles_result.scalars().all())
        
        # Also get competitor articles for sources
        competitor_articles_stmt = (
            select(CompetitorArticle)
            .where(
                CompetitorArticle.topic_id == cluster.topic_id,
                CompetitorArticle.is_valid == True,  # noqa: E712
            )
            .limit(50)  # Limit for performance
        )
        competitor_articles_result = await db.execute(competitor_articles_stmt)
        competitor_articles = list(competitor_articles_result.scalars().all())
        
        # Extract sources (unique domains from competitor articles)
        sources = list(set(comp.domain for comp in competitor_articles if comp.domain))
        sources = sources[:5]  # Limit to 5 sources
        
        # Get most recent publish date
        publish_date = None
        all_dates = [
            art.published_date for art in client_articles + competitor_articles
            if art.published_date
        ]
        if all_dates:
            most_recent = max(all_dates)
            publish_date = most_recent.strftime("%Y-%m-%d")
        
        # Calculate average read time from articles
        read_time = None
        all_word_counts = [
            art.word_count for art in client_articles + competitor_articles
            if art.word_count > 0
        ]
        if all_word_counts:
            avg_word_count = sum(all_word_counts) / len(all_word_counts)
            read_time = _calculate_read_time(int(avg_word_count))
        
        # Extract keywords from top_terms
        keywords = []
        if cluster.top_terms:
            terms = cluster.top_terms.get("terms", [])
            if isinstance(terms, list):
                # Extract first 5-10 keywords
                keywords = [str(t.get("word", t) if isinstance(t, dict) else t) for t in terms[:10]]
        
        # Build topic detail
        topic_detail = TopicDetail(
            id=_slugify_topic_id(cluster.topic_id, cluster.label),
            title=cluster.label,
            summary=synthesis,
            keywords=keywords,
            publish_date=publish_date,
            read_time=read_time,
            engagement=None,  # Not available in database
            category=cluster.scope,  # Use scope as category
            relevance_score=relevance_score,
            trend=trend,
            sources=sources if sources else None,
        )
        
        topics_list.append(topic_detail)
    
    # Sort by relevance_score (descending), then by title
    topics_list.sort(key=lambda t: (-(t.relevance_score or 0), t.title))
    
    return DomainTopicsResponse(
        domain=domain_topic,
        count=len(topics_list),
        topics=topics_list,
    )


async def _get_topic_details(
    db: AsyncSession,
    topic_id_slug: str,
    site_client: str,
    domain_topic: str,
) -> Any:
    """
    Get detailed information for a specific topic.
    
    Args:
        db: Database session
        topic_id_slug: Topic ID slug (e.g., "edge-cloud-hybride-5")
        site_client: Client site identifier (e.g., "innosys", "innosys.fr", or "https://innosys.fr")
        domain_topic: Activity domain label
        
    Returns:
        TopicDetailsResponse with complete topic details
        
    Raises:
        HTTPException: If topic not found
    """
    from python_scripts.api.schemas.responses import (
        TopicDetailsResponse,
        CompetitorDetail,
        SourceDetail,
        TrendDetail,
    )
    from python_scripts.database.crud_llm_results import get_article_recommendations_by_topic_cluster
    from python_scripts.database.models import ArticleRecommendation
    
    # 1. Normalize site_client to extract domain from URL if needed
    normalized_client = _normalize_site_client(site_client)
    
    # 2. Map site_client to domain and get profile
    # Try normalized client first, then common patterns
    domain_candidates = [
        normalized_client,
        f"{normalized_client}.fr",
        f"{normalized_client}.com",
    ]
    
    profile = None
    for candidate_domain in domain_candidates:
        profile = await get_site_profile_by_domain(db, candidate_domain)
        if profile:
            break
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for client: {site_client}",
        )
    
    # 2. Verify domain_topic exists
    activity_domains = profile.activity_domains or {}
    primary_domains = activity_domains.get("primary_domains", [])
    secondary_domains = activity_domains.get("secondary_domains", [])
    all_domains = primary_domains + secondary_domains
    
    if domain_topic not in all_domains:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain topic '{domain_topic}' not found in activity domains for {profile.domain}",
        )
    
    # 3. Get latest trend pipeline execution
    stmt = (
        select(TrendPipelineExecution)
        .where(
            TrendPipelineExecution.client_domain == profile.domain,
            TrendPipelineExecution.stage_1_clustering_status == "completed",
            TrendPipelineExecution.is_valid == True,  # noqa: E712
        )
        .order_by(desc(TrendPipelineExecution.start_time))
        .limit(1)
    )
    result = await db.execute(stmt)
    trend_execution = result.scalar_one_or_none()
    
    if not trend_execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed trend pipeline execution found for {profile.domain}",
        )
    
    # 4. Extract topic_id from slug
    topic_id = _extract_topic_id_from_slug(topic_id_slug)
    if topic_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid topic_id format: {topic_id_slug}",
        )
    
    # 5. Get topic cluster
    cluster = await _get_cluster_by_topic_id(
        db, trend_execution.id, topic_id
    )
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic cluster not found for topic_id: {topic_id}",
        )
    
    # 6. Get trend analysis (summary, opportunities)
    trend_analyses = await get_trend_analyses_by_topic_cluster(db, cluster.id)
    trend_analysis = trend_analyses[0] if trend_analyses else None
    
    synthesis = trend_analysis.synthesis if trend_analysis else cluster.label
    opportunities = trend_analysis.opportunities if trend_analysis else None
    if isinstance(opportunities, list):
        opportunities = opportunities
    elif isinstance(opportunities, dict):
        opportunities = opportunities.get("items", []) if isinstance(opportunities.get("items"), list) else []
    else:
        opportunities = []
    
    # 7. Get temporal metrics (for trend and publish_date)
    temporal_metrics = await get_temporal_metrics_by_topic_cluster(db, cluster.id)
    latest_metric = temporal_metrics[0] if temporal_metrics else None
    
    # 8. Get articles (client + competitor) for dates, sources, read_time
    client_articles_stmt = (
        select(ClientArticle)
        .where(
            ClientArticle.site_profile_id == profile.id,
            ClientArticle.topic_id == cluster.topic_id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    client_articles_result = await db.execute(client_articles_stmt)
    client_articles = list(client_articles_result.scalars().all())
    
    competitor_articles_stmt = (
        select(CompetitorArticle)
        .where(
            CompetitorArticle.topic_id == cluster.topic_id,
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
        .order_by(desc(CompetitorArticle.published_date))
        .limit(20)  # Top 20 for competitors list
    )
    competitor_articles_result = await db.execute(competitor_articles_stmt)
    competitor_articles = list(competitor_articles_result.scalars().all())
    
    # 9. Extract keywords from top_terms
    keywords = []
    if cluster.top_terms:
        terms = cluster.top_terms.get("terms", [])
        if isinstance(terms, list):
            keywords = [
                str(t.get("word", t) if isinstance(t, dict) else t)
                for t in terms[:10]
            ]
    
    # 10. Get most recent publish date
    publish_date = None
    all_dates = [
        art.published_date for art in client_articles + competitor_articles
        if art.published_date
    ]
    if all_dates:
        most_recent = max(all_dates)
        publish_date = most_recent.strftime("%Y-%m-%d")
    
    # 11. Calculate read time
    read_time = None
    all_word_counts = [
        art.word_count for art in client_articles + competitor_articles
        if art.word_count > 0
    ]
    if all_word_counts:
        avg_word_count = sum(all_word_counts) / len(all_word_counts)
        read_time = _calculate_read_time(int(avg_word_count))
    
    # 12. Calculate relevance score
    relevance_score = None
    if cluster.coherence_score:
        relevance_score = int(float(cluster.coherence_score) * 100)
    elif latest_metric and latest_metric.volume:
        relevance_score = min(100, int((latest_metric.volume / 10)))
    
    # 13. Determine trend
    trend = None
    if latest_metric:
        trend_label = _determine_trend(
            float(latest_metric.velocity) if latest_metric.velocity else None
        )
        if trend_label:
            # Get previous metric for delta calculation
            previous_metric = temporal_metrics[1] if len(temporal_metrics) > 1 else None
            delta = _calculate_trend_delta(
                latest_metric.velocity,
                previous_metric.velocity if previous_metric else None,
            )
            
            trend = TrendDetail(
                label=trend_label,
                delta=delta,
            )
    
    # 14. Build competitors list (top 5)
    competitors = None
    if competitor_articles:
        competitors = []
        for comp_art in competitor_articles[:5]:  # Top 5
            competitors.append(CompetitorDetail(
                name=comp_art.domain,
                title=comp_art.title,
                published_date=comp_art.published_date.strftime("%Y-%m-%d") if comp_art.published_date else None,
                performance=None,  # Not available
                strengths=None,  # Not available
                weaknesses=None,  # Not available
            ))
    
    # 15. Get article recommendations for angles and key_points
    article_recommendations = await get_article_recommendations_by_topic_cluster(
        db, cluster.id
    )
    # Sort by differentiation_score descending
    article_recommendations = sorted(
        article_recommendations,
        key=lambda x: x.differentiation_score if x.differentiation_score else 0,
        reverse=True,
    )[:3]  # Top 3
    
    # 16. Extract key_points from first recommendation
    key_points = None
    if article_recommendations and article_recommendations[0].outline:
        key_points = _extract_key_points_from_outline(article_recommendations[0].outline)
    
    # 17. Build angles from opportunities and recommendations
    angles = None
    if opportunities or article_recommendations:
        angles = _transform_opportunities_to_angles(
            opportunities,
            article_recommendations,
        )
    
    # 18. Build sources list
    sources = None
    if competitor_articles:
        unique_domains = list(set(comp.domain for comp in competitor_articles if comp.domain))
        sources = []
        for domain in unique_domains[:5]:  # Top 5 sources
            # Get most recent article from this domain
            domain_articles = [a for a in competitor_articles if a.domain == domain and a.published_date]
            if domain_articles:
                most_recent = max(domain_articles, key=lambda a: a.published_date)
                
                sources.append(SourceDetail(
                    name=domain,
                    type=None,  # Not available
                    credibility=None,  # Not available
                    last_update=most_recent.published_date.strftime("%Y-%m-%d") if most_recent.published_date else None,
                    relevant_content=None,  # Not available
                ))
    
    # 19. Generate predictions
    predictions = None
    if latest_metric or article_recommendations:
        effort_level = article_recommendations[0].effort_level if article_recommendations else None
        diff_score = article_recommendations[0].differentiation_score if article_recommendations else None
        volume = latest_metric.volume if latest_metric else 0
        predictions = _generate_predictions(volume, effort_level, diff_score)
    
    # 20. Build response
    return TopicDetailsResponse(
        id=_slugify_topic_id(cluster.topic_id, cluster.label),
        title=cluster.label,
        publish_date=publish_date,
        read_time=read_time,
        relevance_score=relevance_score,
        category=cluster.scope,
        summary=synthesis,
        keywords=keywords,
        key_points=key_points,
        competitors=competitors,
        angles=angles,
        sources=sources,
        predictions=predictions,
        trend=trend,
    )


router = APIRouter(prefix="/sites", tags=["sites"])


async def run_analysis_background(
    domain: str,
    max_pages: int,
    execution_id: UUID,
) -> None:
    """
    Background task to run editorial analysis.

    Args:
        domain: Domain to analyze
        max_pages: Maximum pages to crawl
        execution_id: Execution ID
    """
    try:
        from python_scripts.database.db_session import AsyncSessionLocal

        # Create new session for background task
        async with AsyncSessionLocal() as db_session:
            orchestrator = EditorialAnalysisOrchestrator(db_session)
            await orchestrator.run_editorial_analysis(
                domain=domain,
                max_pages=max_pages,
                execution_id=execution_id,
            )
    except Exception as e:
        logger.error(
            "Background analysis failed",
            execution_id=str(execution_id),
            domain=domain,
            error=str(e),
        )


@router.post(
    "/analyze",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start editorial analysis",
    description="""
    Start an editorial analysis workflow for a domain.
    
    This endpoint:
    1. Crawls pages from the domain (via sitemap or homepage)
    2. Analyzes editorial style using multiple LLMs (Llama3, Mistral, Phi3)
    3. Creates/updates the site profile with editorial characteristics
    4. Returns an execution_id for tracking progress
    
    Use the execution_id to:
    - Poll status: GET /api/v1/executions/{execution_id}
    - Stream progress: WebSocket /api/v1/executions/{execution_id}/stream
    - Get results: GET /api/v1/sites/{domain}
    """,
    responses={
        202: {
            "description": "Analysis started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "pending",
                        "start_time": None,
                        "estimated_duration_minutes": None,
                    }
                }
            }
        }
    },
)
async def analyze_site(
    request: SiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start editorial analysis for a domain.

    This workflow analyzes the editorial style of a website by:
    - Discovering pages via sitemap
    - Crawling and extracting content
    - Running multi-LLM analysis (language level, tone, audience, keywords, etc.)
    - Creating a comprehensive editorial profile

    Args:
        request: Analysis request with domain and max_pages
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id for tracking
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/sites/analyze" \\
          -H "Content-Type: application/json" \\
          -d '{"domain": "innosys.fr", "max_pages": 50}'
        ```
        
        Response:
        ```json
        {
            "execution_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "pending",
            "start_time": null,
            "estimated_duration_minutes": null
        }
        ```
    """
    try:
        from python_scripts.database.crud_executions import create_workflow_execution

        # Create execution record
        execution = await create_workflow_execution(
            db,
            workflow_type="editorial_analysis",
            input_data={"domain": request.domain, "max_pages": request.max_pages},
            status="pending",
        )

        # Start background task
        background_tasks.add_task(
            run_analysis_background,
            request.domain,
            request.max_pages,
            execution.execution_id,
        )

        logger.info(
            "Analysis started",
            execution_id=str(execution.execution_id),
            domain=request.domain,
        )

        return ExecutionResponse(
            execution_id=execution.execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except Exception as e:
        logger.error("Failed to start analysis", domain=request.domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {e}",
        )


@router.get(
    "/topics",
    response_model=DomainTopicsResponse,
    summary="Get topics by activity domain",
    description="""
    Get topics (clusters) for a specific activity domain and client site.
    
    Returns topics discovered by the trend pipeline, filtered by relevance to the domain.
    Each topic includes summary, keywords, engagement metrics (if available), and sources.
    
    Example:
        GET /api/v1/sites/topics?domain=cyber&site_client=innosys
    """,
    responses={
        200: {
            "description": "Topics retrieved successfully",
        },
        404: {
            "description": "Site profile or domain not found, or no trend pipeline execution",
        },
    },
)
async def get_topics_by_domain(
    domain_topic: str = Query(..., description="Activity domain label (e.g., 'cyber')", alias="domain"),
    site_client: str = Query(..., description="Client site identifier (e.g., 'innosys')"),
    db: AsyncSession = Depends(get_db),
) -> DomainTopicsResponse:
    """
    Get topics for a specific activity domain.
    
    Args:
        domain_topic: Activity domain label (e.g., "cyber")
        site_client: Client site identifier (e.g., "innosys")
        db: Database session
        
    Returns:
        DomainTopicsResponse with list of topics
        
    Raises:
        HTTPException: 404 if site profile, domain, or trend pipeline not found
    """
    return await _get_topics_by_domain(db, site_client, domain_topic)


@router.get(
    "/topics/{topic_id}/details",
    response_model=TopicDetailsResponse,
    summary="Get detailed topic information",
    description="""
    Get comprehensive details for a specific topic.
    
    Returns detailed information including:
    - Basic topic information (title, summary, keywords)
    - Competitor articles analysis
    - Editorial angles and opportunities
    - Sources and metrics
    - Predictions and trends
    
    Example:
        GET /api/v1/sites/topics/erpnext_erp_votre-11/details?domain=Cloud%20Infrastructure%20Management&site_client=innosys.fr
    """,
    responses={
        200: {
            "description": "Topic details retrieved successfully",
        },
        404: {
            "description": "Topic, site profile, or domain not found",
        },
        400: {
            "description": "Invalid topic_id format",
        },
    },
)
async def get_topic_details(
    topic_id: str = Path(..., description="Topic identifier (slug)", examples=["erpnext_erp_votre-11"]),
    domain_topic: str = Query(..., alias="domain", description="Activity domain label", examples=["Cloud Infrastructure Management"]),
    site_client: str = Query(..., description="Client site identifier", examples=["innosys.fr"]),
    db: AsyncSession = Depends(get_db),
) -> TopicDetailsResponse:
    """
    Get detailed information for a specific topic.
    
    Args:
        topic_id: Topic identifier (slug format)
        domain_topic: Activity domain label
        site_client: Client site identifier
        db: Database session
        
    Returns:
        TopicDetailsResponse with complete topic details
    """
    return await _get_topic_details(db, topic_id, site_client, domain_topic)


@router.get(
    "/{domain}",
    response_model=SiteProfileResponse,
    summary="Get site profile",
    description="Get the latest editorial profile for a domain.",
)
async def get_site_profile(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> SiteProfileResponse:
    """
    Get site profile by domain.

    Args:
        domain: Domain name
        db: Database session

    Returns:
        Site profile response

    Raises:
        HTTPException: If profile not found
    """
    profile = await get_site_profile_by_domain(db, domain)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )

    return SiteProfileResponse(
        domain=profile.domain,
        analysis_date=profile.analysis_date,
        language_level=profile.language_level,
        editorial_tone=profile.editorial_tone,
        target_audience=_safe_json_field(profile.target_audience),
        activity_domains=_safe_json_field(profile.activity_domains),
        content_structure=_safe_json_field(profile.content_structure),
        keywords=_safe_json_field(profile.keywords),
        style_features=_safe_json_field(profile.style_features),
        pages_analyzed=profile.pages_analyzed,
        llm_models_used=_safe_json_field(profile.llm_models_used),
    )


@router.get(
    "",
    response_model=List[SiteProfileResponse],
    summary="List all analyzed sites",
    description="Get a list of all domains that have been analyzed.",
)
async def list_sites(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[SiteProfileResponse]:
    """
    List all analyzed sites.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        db: Database session

    Returns:
        List of site profiles
    """
    profiles = await list_site_profiles(db, limit=limit, offset=offset)
    return [
        SiteProfileResponse(
            domain=profile.domain,
            analysis_date=profile.analysis_date,
            language_level=profile.language_level,
            editorial_tone=profile.editorial_tone,
            target_audience=_safe_json_field(profile.target_audience),
            activity_domains=_safe_json_field(profile.activity_domains),
            content_structure=_safe_json_field(profile.content_structure),
            keywords=_safe_json_field(profile.keywords),
            style_features=_safe_json_field(profile.style_features),
            pages_analyzed=profile.pages_analyzed,
            llm_models_used=_safe_json_field(profile.llm_models_used),
        )
        for profile in profiles
    ]


def compare_metrics(
    current_profile: SiteProfile,
    previous_profile: Optional[SiteProfile],
) -> List[MetricComparison]:
    """
    Compare metrics between current and previous analysis.

    Args:
        current_profile: Current site profile
        previous_profile: Previous site profile (if available)

    Returns:
        List of metric comparisons
    """
    comparisons: List[MetricComparison] = []

    if not previous_profile:
        return comparisons

    # Compare pages_analyzed
    if current_profile.pages_analyzed and previous_profile.pages_analyzed:
        change = (
            (current_profile.pages_analyzed - previous_profile.pages_analyzed)
            / previous_profile.pages_analyzed
            * 100
            if previous_profile.pages_analyzed > 0
            else 0
        )
        trend = "increasing" if change > 0 else "decreasing" if change < 0 else "stable"
        comparisons.append(
            MetricComparison(
                metric_name="pages_analyzed",
                current_value=current_profile.pages_analyzed,
                previous_value=previous_profile.pages_analyzed,
                change=round(change, 2),
                trend=trend,
            )
        )

    # Compare language_level (if changed)
    if current_profile.language_level and previous_profile.language_level:
        if current_profile.language_level != previous_profile.language_level:
            comparisons.append(
                MetricComparison(
                    metric_name="language_level",
                    current_value=current_profile.language_level,
                    previous_value=previous_profile.language_level,
                    change=None,
                    trend="changed",
                )
            )

    # Compare editorial_tone (if changed)
    if current_profile.editorial_tone and previous_profile.editorial_tone:
        if current_profile.editorial_tone != previous_profile.editorial_tone:
            comparisons.append(
                MetricComparison(
                    metric_name="editorial_tone",
                    current_value=current_profile.editorial_tone,
                    previous_value=previous_profile.editorial_tone,
                    change=None,
                    trend="changed",
                )
            )

    return comparisons


@router.get(
    "/{domain}/history",
    response_model=SiteHistoryResponse,
    summary="Get site analysis history",
    description="Get historical analyses for a domain with metric comparisons.",
)
async def get_site_history_endpoint(
    domain: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> SiteHistoryResponse:
    """
    Get historical analyses for a domain.

    Args:
        domain: Domain name
        limit: Maximum number of historical records
        db: Database session

    Returns:
        Site history response with comparisons

    Raises:
        HTTPException: If no history found
    """
    # Get current profile
    current_profile = await get_site_profile_by_domain(db, domain)
    if not current_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )

    # Get historical profiles
    history_profiles = await get_site_history(db, domain, limit=limit)

    if not history_profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis history found for domain: {domain}",
        )

    # Convert to history entries
    history_entries = [
        SiteHistoryEntry(
            analysis_date=profile.analysis_date,
            language_level=profile.language_level,
            editorial_tone=profile.editorial_tone,
            pages_analyzed=profile.pages_analyzed,
            target_audience=_safe_json_field(profile.target_audience),
            activity_domains=_safe_json_field(profile.activity_domains),
            content_structure=_safe_json_field(profile.content_structure),
            keywords=_safe_json_field(profile.keywords),
            style_features=_safe_json_field(profile.style_features),
        )
        for profile in history_profiles
    ]

    # Compare metrics (current vs previous)
    previous_profile = history_profiles[1] if len(history_profiles) > 1 else None
    metric_comparisons = compare_metrics(current_profile, previous_profile)

    return SiteHistoryResponse(
        domain=domain,
        total_analyses=len(history_profiles),
        history=history_entries,
        metric_comparisons=metric_comparisons if metric_comparisons else None,
        first_analysis_date=history_profiles[-1].analysis_date if history_profiles else None,
        last_analysis_date=history_profiles[0].analysis_date if history_profiles else None,
    )


# ============================================================
# Audit endpoint functions
# ============================================================

async def wait_for_execution_completion(
    db: AsyncSession,
    execution_id: UUID,
    timeout: int = 600,
    poll_interval: int = 5,
) -> None:
    """
    Wait for an execution to complete.
    
    Args:
        db: Database session
        execution_id: Execution ID to wait for
        timeout: Maximum wait time in seconds
        poll_interval: Polling interval in seconds
        
    Raises:
        TimeoutError: If execution doesn't complete within timeout
        RuntimeError: If execution fails
    """
    from datetime import timedelta
    from python_scripts.database.crud_executions import get_workflow_execution
    
    start_time = datetime.now()
    timeout_time = start_time + timedelta(seconds=timeout)
    
    while datetime.now() < timeout_time:
        execution = await get_workflow_execution(db, execution_id)
        
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        if execution.status == "completed":
            return
        
        if execution.status == "failed":
            raise RuntimeError(
                f"Execution {execution_id} failed: {execution.error_message or 'Unknown error'}"
            )
        
        await asyncio.sleep(poll_interval)
    
    raise TimeoutError(
        f"Execution {execution_id} did not complete within {timeout} seconds"
    )


async def run_missing_workflows_chain(
    domain: str,
    orchestrator_execution_id: UUID,
    needs_analysis: bool,
    needs_competitors: bool,
    needs_scraping: bool,
    needs_client_scraping: bool,
    needs_trend_pipeline: bool,
    profile_id: Optional[int],
) -> None:
    """
    Execute the chain of missing workflows sequentially.
    
    Order:
    1. Editorial analysis (sites/analyze)
    2. Competitor search (competitors/search) - after #1
    3. Client scraping (discovery/client-scrape) - after #1
    4. Competitor scraping (discovery/scrape) - after #2
    5. Trend pipeline (trend-pipeline/analyze) - after #3 and #4
    
    Args:
        domain: Domain name
        orchestrator_execution_id: Orchestrator execution ID
        needs_analysis: Whether editorial analysis is needed
        needs_competitors: Whether competitor search is needed
        needs_scraping: Whether competitor scraping is needed
        needs_client_scraping: Whether client scraping is needed
        needs_trend_pipeline: Whether trend pipeline is needed
        profile_id: Site profile ID (if already exists)
    """
    from python_scripts.database.db_session import AsyncSessionLocal
    from python_scripts.database.crud_executions import (
        get_workflow_execution,
        update_workflow_execution,
        create_workflow_execution,
    )
    from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
    from python_scripts.agents.scrapping import EnhancedScrapingAgent
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    async with AsyncSessionLocal() as db:
        failed_workflows = []  # Liste des workflows échoués (workflow_type, error_message)
        orchestrator = EditorialAnalysisOrchestrator(db)
        current_profile_id = profile_id
        
        try:
            # Étape 1: Editorial Analysis (CRITIQUE - doit réussir)
            if needs_analysis:
                try:
                    logger.info("Step 1: Starting editorial analysis", domain=domain)
                    analysis_execution = await create_workflow_execution(
                        db,
                        workflow_type="editorial_analysis",
                        input_data={"domain": domain, "max_pages": 50},
                        status="pending",
                        parent_execution_id=orchestrator_execution_id,
                    )
                    
                    await orchestrator.run_editorial_analysis(
                        domain=domain,
                        max_pages=50,
                        execution_id=analysis_execution.execution_id,
                    )
                    
                    await wait_for_execution_completion(
                        db, analysis_execution.execution_id, timeout=600
                    )
                    
                    # Vérifier le succès
                    analysis_exec = await get_workflow_execution(db, analysis_execution.execution_id)
                    if analysis_exec and analysis_exec.status == "completed":
                        await update_workflow_execution(
                            db,
                            analysis_exec,
                            was_success=True,
                        )
                        # Récupérer le profile créé
                        profile = await get_site_profile_by_domain(db, domain)
                        if profile:
                            current_profile_id = profile.id
                    else:
                        raise Exception("Editorial analysis did not complete successfully")
                        
                except Exception as e:
                    logger.error(
                        "Editorial analysis failed (critical)",
                        domain=domain,
                        error=str(e),
                        exc_info=True,
                    )
                    # Marquer l'exécution comme échouée
                    if 'analysis_execution' in locals():
                        analysis_exec = await get_workflow_execution(db, analysis_execution.execution_id)
                        if analysis_exec:
                            await update_workflow_execution(
                                db,
                                analysis_exec,
                                status="failed",
                                error_message=str(e),
                                was_success=False,
                            )
                    failed_workflows.append(("editorial_analysis", str(e)))
                    # Ne pas continuer si l'analyse échoue (critique)
                    raise
            
            # Étape 2: Competitor Search (NON-CRITIQUE)
            if needs_competitors:
                try:
                    logger.info("Step 2: Starting competitor search", domain=domain)
                    competitor_execution = await create_workflow_execution(
                        db,
                        workflow_type="competitor_search",
                        input_data={"domain": domain, "max_competitors": 100},
                        status="pending",
                        parent_execution_id=orchestrator_execution_id,
                    )
                    
                    await orchestrator.run_competitor_search(
                        domain=domain,
                        max_competitors=100,
                        execution_id=competitor_execution.execution_id,
                    )
                    
                    await wait_for_execution_completion(
                        db, competitor_execution.execution_id, timeout=300
                    )
                    
                    # Vérifier le succès
                    competitor_exec = await get_workflow_execution(db, competitor_execution.execution_id)
                    if competitor_exec and competitor_exec.status == "completed":
                        await update_workflow_execution(
                            db,
                            competitor_exec,
                            was_success=True,
                        )
                        
                        # Auto-validate all competitors found (appel automatique de la validation)
                        try:
                            from python_scripts.api.routers.competitors import auto_validate_competitors
                            logger.info(
                                "Auto-validating competitors after search",
                                domain=domain,
                                execution_id=str(competitor_exec.execution_id),
                            )
                            await auto_validate_competitors(
                                db_session=db,
                                domain=domain,
                                execution=competitor_exec,
                            )
                            logger.info(
                                "Auto-validation completed",
                                domain=domain,
                                execution_id=str(competitor_exec.execution_id),
                            )
                        except Exception as e:
                            logger.warning(
                                "Auto-validation failed, continuing anyway",
                                domain=domain,
                                error=str(e),
                                exc_info=True,
                            )
                            # Ne pas faire échouer le workflow si la validation échoue
                    else:
                        raise Exception("Competitor search did not complete successfully")
                        
                except Exception as e:
                    logger.error(
                        "Competitor search failed, continuing...",
                        domain=domain,
                        error=str(e),
                        exc_info=True,
                    )
                    # Marquer l'exécution comme échouée
                    if 'competitor_execution' in locals():
                        competitor_exec = await get_workflow_execution(db, competitor_execution.execution_id)
                        if competitor_exec:
                            await update_workflow_execution(
                                db,
                                competitor_exec,
                                status="failed",
                                error_message=str(e),
                                was_success=False,
                            )
                    failed_workflows.append(("competitor_search", str(e)))
                    # Ne pas raise, continuer avec les autres workflows
            
            # Étape 3: Client Scraping (SEMI-CRITIQUE)
            if needs_client_scraping and current_profile_id:
                try:
                    logger.info("Step 3: Starting client site scraping", domain=domain)
                    
                    # Créer un WorkflowExecution pour le client scraping
                    client_scraping_execution = await create_workflow_execution(
                        db,
                        workflow_type="client_scraping",
                        input_data={"domain": domain, "max_articles": 100},
                        status="running",
                        parent_execution_id=orchestrator_execution_id,
                    )
                    
                    scraping_agent = EnhancedScrapingAgent(min_word_count=150)
                    await scraping_agent.discover_and_scrape_articles(
                        db,
                        domain,
                        max_articles=100,
                        is_client_site=True,
                        site_profile_id=current_profile_id,
                        force_reprofile=False,
                    )
                    await update_workflow_execution(
                        db,
                        client_scraping_execution,
                        status="completed",
                        was_success=True,
                    )
                    
                    # Generate and save domain summaries after scraping (issue #002)
                    try:
                        current_profile = await get_site_profile_by_domain(db, domain)
                        if current_profile:
                            # Get trend execution if available
                            trend_exec = await _check_trend_pipeline(db, domain)
                            await _save_domain_summaries_to_profile(
                                db,
                                current_profile,
                                trend_execution=trend_exec,
                            )
                            logger.info(
                                "Domain summaries generated after client scraping",
                                domain=domain,
                            )
                    except Exception as e:
                        # Log but don't fail the workflow
                        logger.warning(
                            "Failed to generate domain summaries after scraping",
                            domain=domain,
                            error=str(e),
                        )
                except Exception as e:
                    logger.error(
                        "Client scraping failed",
                        domain=domain,
                        error=str(e),
                        exc_info=True,
                    )
                    # Marquer l'exécution comme échouée
                    if 'client_scraping_execution' in locals():
                        await update_workflow_execution(
                            db,
                            client_scraping_execution,
                            status="failed",
                            error_message=str(e),
                            was_success=False,
                        )
                    failed_workflows.append(("client_scraping", str(e)))
                    # Continuer quand même (peut avoir des données partielles)
            
            # Étape 4: Competitor Scraping (NON-CRITIQUE)
            if needs_scraping:
                try:
                    logger.info("Step 4: Starting competitor scraping", domain=domain)
                    # Récupérer les concurrents validés
                    stmt = (
                        select(WorkflowExecution)
                        .where(
                            WorkflowExecution.workflow_type == "competitor_search",
                            WorkflowExecution.status == "completed",
                            WorkflowExecution.input_data["domain"].astext == domain,
                        )
                        .order_by(desc(WorkflowExecution.start_time))
                        .limit(1)
                    )
                    result = await db.execute(stmt)
                    competitor_exec = result.scalar_one_or_none()
                    
                    if competitor_exec and competitor_exec.output_data:
                        competitors_data = competitor_exec.output_data.get("competitors", [])
                        # Use same filter as trend pipeline for consistency
                        competitor_domains = []
                        for c in competitors_data:
                            validation_status = c.get("validation_status", "validated")
                            validated = c.get("validated", False)
                            excluded = c.get("excluded", False)
                            competitor_domain = c.get("domain")

                            # Include only validated or manual competitors (not excluded)
                            if competitor_domain and not excluded and (validation_status in ["validated", "manual"] or validated):
                                competitor_domains.append(competitor_domain)

                        if competitor_domains:
                            logger.info(
                                "Starting scraping for validated competitors",
                                domain=domain,
                                competitor_count=len(competitor_domains),
                                domains=competitor_domains[:50],  # Log first 10 domains
                            )
                            scraping_execution = await create_workflow_execution(
                                db,
                                workflow_type="enhanced_scraping",
                                input_data={
                                    "client_domain": domain,
                                    "domains": competitor_domains,
                                    "max_articles": 100,
                                },
                                status="running",
                                parent_execution_id=orchestrator_execution_id,
                            )

                            scraping_agent = EnhancedScrapingAgent(min_word_count=150)
                            for comp_domain in competitor_domains:
                                await scraping_agent.discover_and_scrape_articles(
                                    db,
                                    comp_domain,
                                    max_articles=100,
                                    is_client_site=False,
                                    site_profile_id=None,
                                    force_reprofile=False,
                                    client_domain=domain,
                                )

                            await update_workflow_execution(
                                db,
                                scraping_execution,
                                status="completed",
                                was_success=True,
                            )
                        else:
                            # No validated competitors found
                            total_competitors = len(competitors_data)
                            logger.warning(
                                "Competitor scraping skipped: no validated competitors",
                                domain=domain,
                                total_competitors_found=total_competitors,
                                validated_competitors=0,
                                recommendation=(
                                    "Validate competitors via /api/v1/competitors/validate endpoint "
                                    "or enable auto-validation in competitor search."
                                )
                            )
                    else:
                        logger.warning(
                            "Competitor scraping skipped: no competitor search results",
                            domain=domain,
                        )
                except Exception as e:
                    logger.error(
                        "Competitor scraping failed, continuing...",
                        domain=domain,
                        error=str(e),
                        exc_info=True,
                    )
                    # Marquer l'exécution comme échouée si elle existe
                    if 'scraping_execution' in locals():
                        await update_workflow_execution(
                            db,
                            scraping_execution,
                            status="failed",
                            error_message=str(e),
                            was_success=False,
                        )
                    failed_workflows.append(("enhanced_scraping", str(e)))
                    # Ne pas raise, continuer avec les autres workflows
            
            # Étape 5: Trend Pipeline (NON-CRITIQUE)
            if needs_trend_pipeline:
                try:
                    logger.info("Step 5: Starting trend pipeline", domain=domain)
                    
                    # Créer un WorkflowExecution pour le trend pipeline
                    trend_execution = await create_workflow_execution(
                        db,
                        workflow_type="trend_pipeline",
                        input_data={
                            "client_domain": domain,
                            "time_window_days": 90,
                        },
                        status="running",
                        parent_execution_id=orchestrator_execution_id,
                    )
                    
                    from uuid import uuid4
                    from python_scripts.api.routers.trend_pipeline import (
                        TrendPipelineRequest,
                        run_trend_pipeline_task,
                    )
                    
                    execution_id = str(uuid4())
                    request = TrendPipelineRequest(
                        client_domain=domain,
                        time_window_days=90,
                        skip_llm=False,
                        skip_gap_analysis=False,
                    )
                    
                    await run_trend_pipeline_task(
                        request=request,
                        db=db,
                        execution_id=execution_id,
                    )
                    
                    # Wait for trend pipeline completion (check via TrendPipelineExecution)
                    from python_scripts.database.models import TrendPipelineExecution
                    from uuid import UUID as UUIDType
                    
                    max_wait = 1200  # 20 minutes
                    start_wait = datetime.now()
                    trend_exec = None
                    while (datetime.now() - start_wait).total_seconds() < max_wait:
                        stmt = (
                            select(TrendPipelineExecution)
                            .where(
                                TrendPipelineExecution.execution_id == UUIDType(execution_id),
                                TrendPipelineExecution.stage_1_clustering_status == "completed",
                                TrendPipelineExecution.stage_2_temporal_status == "completed",
                                TrendPipelineExecution.stage_3_llm_status == "completed",
                            )
                        )
                        result = await db.execute(stmt)
                        trend_exec = result.scalar_one_or_none()
                        
                        if trend_exec:
                            break
                        
                        await asyncio.sleep(10)
                    
                    # Vérifier si timeout (P1-9)
                    if not trend_exec:
                        elapsed = (datetime.now() - start_wait).total_seconds()
                        error_msg = f"Trend pipeline did not complete within {max_wait}s (elapsed: {elapsed:.0f}s)"
                        logger.error(
                            "Trend pipeline timeout",
                            execution_id=execution_id,
                            elapsed=elapsed,
                            domain=domain,
                        )
                        await update_workflow_execution(
                            db,
                            trend_execution,
                            status="failed",
                            error_message=error_msg,
                            was_success=False,
                        )
                        failed_workflows.append(("trend_pipeline", error_msg))
                    else:
                        await update_workflow_execution(
                            db,
                            trend_execution,
                            status="completed",
                            was_success=True,
                        )
                except Exception as e:
                    logger.error(
                        "Trend pipeline failed",
                        domain=domain,
                        error=str(e),
                        exc_info=True,
                    )
                    # Marquer l'exécution comme échouée
                    if 'trend_execution' in locals():
                        await update_workflow_execution(
                            db,
                            trend_execution,
                            status="failed",
                            error_message=str(e),
                            was_success=False,
                        )
                    failed_workflows.append(("trend_pipeline", str(e)))
                    # Ne pas raise, continuer
            
            # Déterminer le statut final de l'orchestrator (P0-3)
            orchestrator_exec = await get_workflow_execution(
                db, orchestrator_execution_id
            )
            if orchestrator_exec:
                if failed_workflows:
                    # Succès partiel
                    status = "completed"  # On garde "completed" mais avec was_success=False
                    error_message = f"Some workflows failed: {', '.join(w[0] for w in failed_workflows)}"
                    was_success = False
                    output_data = {"failed_workflows": failed_workflows}
                else:
                    # Succès complet
                    status = "completed"
                    error_message = None
                    was_success = True
                    output_data = None

                await update_workflow_execution(
                    db,
                    orchestrator_exec,
                    status=status,
                    error_message=error_message,
                    was_success=was_success,
                    output_data=output_data,
                )

            logger.info(
                "Missing workflows completed",
                domain=domain,
                orchestrator_execution_id=str(orchestrator_execution_id),
                status=status,
                failed_count=len(failed_workflows),
                failed_workflows=[w[0] for w in failed_workflows] if failed_workflows else [],
            )
            
        except Exception as e:
            # Erreur critique (editorial_analysis ou autre erreur non gérée)
            logger.error(
                "Critical error in workflows chain",
                domain=domain,
                error=str(e),
                exc_info=True,
            )
            orchestrator_exec = await get_workflow_execution(
                db, orchestrator_execution_id
            )
            if orchestrator_exec:
                await update_workflow_execution(
                    db,
                    orchestrator_exec,
                    status="failed",
                    error_message=str(e),
                    was_success=False,
                )


async def _get_audit_status(
    db: AsyncSession,
    orchestrator_execution_id: UUID,
    domain: str,
) -> AuditStatusResponse:
    """
    Récupère le statut global de l'audit avec tous les workflows enfants.
    
    Args:
        db: Session de base de données
        orchestrator_execution_id: ID de l'orchestrator
        domain: Domaine analysé
        
    Returns:
        Statut global de l'audit
    """
    from datetime import timedelta, timezone
    from python_scripts.database.models import WorkflowExecution
    
    # Récupérer l'orchestrator
    orchestrator = await get_workflow_execution(db, orchestrator_execution_id)
    if not orchestrator:
        raise HTTPException(
            status_code=404,
            detail=f"Orchestrator execution not found: {orchestrator_execution_id}"
        )
    
    # P0-2: Vérifier le timeout global (1 heure maximum)
    now = datetime.now(timezone.utc)
    MAX_ORCHESTRATOR_DURATION_SECONDS = 3600  # 1 heure
    if orchestrator.start_time and orchestrator.status == "running":
        elapsed_seconds = (now - orchestrator.start_time).total_seconds()
        if elapsed_seconds > MAX_ORCHESTRATOR_DURATION_SECONDS:
            # Timeout dépassé : marquer comme failed
            from python_scripts.database.crud_executions import update_workflow_execution
            logger.warning(
                "Orchestrator timeout exceeded, marking as failed",
                execution_id=str(orchestrator_execution_id),
                elapsed_seconds=elapsed_seconds,
                max_duration=MAX_ORCHESTRATOR_DURATION_SECONDS,
            )
            await update_workflow_execution(
                db,
                orchestrator,
                status="failed",
                error_message=f"Orchestrator timeout exceeded after {elapsed_seconds:.0f} seconds (max: {MAX_ORCHESTRATOR_DURATION_SECONDS}s)",
            )
            # Recharger l'orchestrator pour avoir le statut mis à jour
            orchestrator = await get_workflow_execution(db, orchestrator_execution_id)
    
    # Récupérer tous les workflows enfants
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.parent_execution_id == orchestrator_execution_id,
            WorkflowExecution.is_valid == True,
        )
        .order_by(WorkflowExecution.created_at)
    )
    result = await db.execute(stmt)
    child_workflows = list(result.scalars().all())
    
    # Mapper les types de workflow vers les noms d'étapes
    workflow_type_to_step = {
        "editorial_analysis": {"step": 1, "name": "Editorial Analysis"},
        "competitor_search": {"step": 2, "name": "Competitor Search"},
        "client_scraping": {"step": 3, "name": "Client Site Scraping"},
        "enhanced_scraping": {"step": 4, "name": "Competitor Scraping"},
        "trend_pipeline": {"step": 5, "name": "Trend Pipeline"},
    }
    
    # Construire la liste des étapes
    workflow_steps = []
    now = datetime.now(timezone.utc)
    
    for child in child_workflows:
        step_info = workflow_type_to_step.get(child.workflow_type, {
            "step": len(workflow_steps) + 1,
            "name": child.workflow_type.replace("_", " ").title()
        })
        
        # Calculer le pourcentage de progression pour cette étape
        progress = None
        if child.status == "completed":
            progress = 100.0
        elif child.status == "running":
            # Estimation basée sur le type de workflow et le temps écoulé
            if child.start_time:
                elapsed = (now - child.start_time).total_seconds()
                estimated_duration = {
                    "editorial_analysis": 600,  # 10 minutes
                    "competitor_search": 300,  # 5 minutes
                    "client_scraping": 180,    # 3 minutes
                    "enhanced_scraping": 600,   # 10 minutes
                    "trend_pipeline": 1200,    # 20 minutes
                }.get(child.workflow_type, 300)
                progress = min(90.0, (elapsed / estimated_duration) * 100)
            else:
                progress = 10.0
        elif child.status == "failed":
            progress = 0.0
        else:
            progress = 0.0
        
        workflow_steps.append(
            WorkflowStepDetail(
                step=step_info["step"],
                name=step_info["name"],
                workflow_type=child.workflow_type,
                status=child.status,
                execution_id=str(child.execution_id),
                start_time=child.start_time,
                end_time=child.end_time,
                duration_seconds=child.duration_seconds,
                error_message=child.error_message,
                progress_percentage=round(progress, 2),
            )
        )
    
    # Calculer les statistiques globales
    total_steps = len(workflow_steps)
    completed_steps = sum(1 for s in workflow_steps if s.status == "completed")
    failed_steps = sum(1 for s in workflow_steps if s.status == "failed")
    running_steps = sum(1 for s in workflow_steps if s.status == "running")
    pending_steps = sum(1 for s in workflow_steps if s.status == "pending")
    
    # Calculer la progression globale
    if total_steps > 0:
        overall_progress = (completed_steps / total_steps) * 100
        # Ajouter une partie de la progression des étapes en cours
        if running_steps > 0:
            running_progress = sum(
                s.progress_percentage or 0 
                for s in workflow_steps 
                if s.status == "running"
            ) / running_steps
            overall_progress += (running_progress / total_steps) * (running_steps / total_steps) * 100
    else:
        overall_progress = 0.0
    
    overall_progress = min(100.0, overall_progress)
    
    # Déterminer le statut global
    if orchestrator.status == "completed":
        overall_status = "completed"
    elif orchestrator.status == "failed":
        overall_status = "failed"
    elif failed_steps > 0 and completed_steps < total_steps:
        overall_status = "partial"
    elif running_steps > 0 or orchestrator.status == "running":
        overall_status = "running"
    else:
        overall_status = "pending"
    
    # Estimer le temps de fin
    estimated_completion = None
    if overall_status in ("running", "pending") and orchestrator.start_time:
        # Estimation basée sur les étapes restantes
        remaining_steps = total_steps - completed_steps
        avg_duration_per_step = 300  # 5 minutes par défaut
        if completed_steps > 0:
            avg_duration = sum(
                s.duration_seconds or 0 
                for s in workflow_steps 
                if s.status == "completed"
            ) / completed_steps
            avg_duration_per_step = avg_duration if avg_duration > 0 else 300
        
        estimated_remaining_seconds = remaining_steps * avg_duration_per_step
        estimated_completion = now + timedelta(seconds=estimated_remaining_seconds)
    
    # Récupérer le statut des données
    profile = await _check_site_profile(db, domain)
    competitors_execution = await _check_competitors(db, domain) if profile else None
    
    client_articles_count = 0
    has_client_articles = False
    if profile:
        count, is_sufficient = await _check_client_articles(db, profile.id)
        client_articles_count = count
        has_client_articles = is_sufficient
    
    competitor_articles_count = 0
    has_competitor_articles = False
    if competitors_execution and competitors_execution.output_data:
        # P0-5: vérification null pour output_data
        competitors_data = competitors_execution.output_data.get("competitors", [])
        competitor_domains = [
            c.get("domain")
            for c in competitors_data
            if c.get("domain")
            and not c.get("excluded", False)
            and (c.get("validated", False) or c.get("manual", False))
        ]
        if competitor_domains:
            count, is_sufficient = await _check_competitor_articles(
                db, competitor_domains, client_domain=domain
            )
            competitor_articles_count = count
            has_competitor_articles = is_sufficient
    
    trend_execution = await _check_trend_pipeline(db, domain) if profile else None
    
    data_status = DataStatus(
        has_profile=profile is not None,
        has_competitors=competitors_execution is not None,
        has_client_articles=has_client_articles,
        has_competitor_articles=has_competitor_articles,
        has_trend_pipeline=trend_execution is not None,
    )
    
    return AuditStatusResponse(
        orchestrator_execution_id=str(orchestrator_execution_id),
        domain=domain,
        overall_status=overall_status,
        overall_progress=round(overall_progress, 2),
        total_steps=total_steps,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        running_steps=running_steps,
        pending_steps=pending_steps,
        workflow_steps=workflow_steps,
        start_time=orchestrator.start_time,
        estimated_completion_time=estimated_completion,
        data_status=data_status,
    )


# Regex pour valider le format d'un domaine
DOMAIN_REGEX = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)


@router.get(
    "/{domain}/audit",
    response_model=Union[SiteAuditResponse, PendingAuditResponse],
    summary="Get complete site audit (auto-launches missing workflows)",
    description="""
    Get complete site audit data.
    
    Strategy:
    1. Check if data exists in database
    2. If exists: retrieve and use it
    3. If missing: launch only the missing workflows
    
    Checks in order:
    - Site profile (site_profiles)
    - Competitors (workflow_executions with competitor_search)
    - Scraped articles (competitor_articles count)
    - Trend pipeline (trend_pipeline_executions)
    
    Returns either:
    - Complete audit data if all data is available
    - Pending response with execution_id if workflows are launched
    """,
)
async def get_site_audit(
    domain: str = Path(
        ...,
        description="Valid domain name (e.g., example.com, innosys.fr)",
        examples=["innosys.fr", "example.com"],
    ),
    include_topics: bool = Query(False, description="Include detailed topics in domains"),
    include_trending: bool = Query(True, description="Include trending topics section"),
    include_analyses: bool = Query(True, description="Include trend analyses section"),
    include_temporal: bool = Query(True, description="Include temporal insights section"),
    include_opportunities: bool = Query(True, description="Include editorial opportunities section"),
    topics_limit: int = Query(10, ge=1, le=50, description="Maximum number of topics per domain"),
    trending_limit: int = Query(15, ge=1, le=100, description="Maximum number of trending topics"),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Union[SiteAuditResponse, PendingAuditResponse]:
    """
    Get site audit with smart data retrieval.
    
    Vérifie chaque source de données et lance seulement ce qui manque.
    
    Args:
        domain: Domain name (validated format)
        include_topics: Include detailed topics in domains (default: False)
        include_trending: Include trending topics section (default: True)
        include_analyses: Include trend analyses section (default: True)
        include_temporal: Include temporal insights section (default: True)
        include_opportunities: Include editorial opportunities section (default: True)
        topics_limit: Maximum number of topics per domain (default: 10, max: 50)
        trending_limit: Maximum number of trending topics (default: 15, max: 100)
        db: Database session
        background_tasks: FastAPI background tasks
        
    Returns:
        Complete audit data or pending response
        
    Raises:
        HTTPException: 422 if domain format is invalid
    """
    # Validation du domaine (P2-8)
    if not DOMAIN_REGEX.match(domain):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid domain format: {domain}. Expected format: example.com",
        )
    
    from python_scripts.database.crud_executions import create_workflow_execution
    
    # ============================================================
    # ÉTAPE 1: Vérifier site_profile (P0-4: gestion d'erreur)
    # ============================================================
    try:
        profile = await _check_site_profile(db, domain)
    except Exception as e:
        logger.warning(
            "Error checking site profile, assuming missing",
            domain=domain,
            error=str(e),
        )
        profile = None
    needs_analysis = not profile
    
    # ============================================================
    # ÉTAPE 2-5: Vérifications en parallèle (P1-1: parallélisation)
    # ============================================================
    # Paralléliser les vérifications indépendantes pour améliorer les performances
    competitors_execution = None
    trend_execution = None
    competitor_articles_count = 0
    client_articles_count = 0
    
    if profile:
        # Lancer les vérifications en parallèle
        try:
            results = await asyncio.gather(
                _check_competitors(db, domain),
                _check_trend_pipeline(db, domain),
                _check_client_articles(db, profile.id),
                return_exceptions=True,
            )
            
            competitors_execution, trend_execution, client_articles_result = results
            
            # Gérer les exceptions (P0-4: gestion d'erreur)
            if isinstance(competitors_execution, Exception):
                logger.warning(
                    "Error checking competitors, assuming missing",
                    domain=domain,
                    error=str(competitors_execution),
                )
                competitors_execution = None
            if isinstance(trend_execution, Exception):
                logger.warning(
                    "Error checking trend pipeline, assuming missing",
                    domain=domain,
                    error=str(trend_execution),
                )
                trend_execution = None
            if isinstance(client_articles_result, Exception):
                logger.warning(
                    "Error checking client articles, assuming missing",
                    domain=domain,
                    error=str(client_articles_result),
                )
                client_articles_count = 0
            else:
                # client_articles_result est un tuple (count, is_sufficient)
                client_articles_count, _ = client_articles_result
        except Exception as e:
            logger.error(
                "Error during parallel checks",
                domain=domain,
                error=str(e),
            )
            # En cas d'erreur globale, considérer que tout manque
            competitors_execution = None
            trend_execution = None
            client_articles_count = 0
    else:
        # Pas de profile : vérifier seulement les concurrents (sans dépendance)
        try:
            competitors_execution = await _check_competitors(db, domain)
            if isinstance(competitors_execution, Exception):
                logger.warning(
                    "Error checking competitors, assuming missing",
                    domain=domain,
                    error=str(competitors_execution),
                )
                competitors_execution = None
        except Exception as e:
            logger.warning(
                "Error checking competitors, assuming missing",
                domain=domain,
                error=str(e),
            )
            competitors_execution = None
    
    needs_competitors = not competitors_execution
    needs_trend_pipeline = not trend_execution
    
    # ============================================================
    # ÉTAPE 3: Vérifier articles scrapés (competitors)
    # ============================================================
    needs_scraping = False
    
    if competitors_execution:
        # Récupérer les domaines des concurrents validés (P0-5: vérification null)
        if competitors_execution.output_data is None:
            competitors_data = []
        else:
            competitors_data = competitors_execution.output_data.get("competitors", [])
        competitor_domains = [
            c.get("domain")
            for c in competitors_data
            if c.get("domain")
            and not c.get("excluded", False)
            and (c.get("validated", False) or c.get("manual", False))
        ]
        
        if competitor_domains:
            # Compter les articles pour ces domaines (PostgreSQL + Qdrant)
            try:
                count, is_sufficient = await _check_competitor_articles(
                    db, competitor_domains, client_domain=domain
                )
                competitor_articles_count = count
                needs_scraping = not is_sufficient
            except Exception as e:
                logger.warning(
                    "Error checking competitor articles, assuming insufficient",
                    domain=domain,
                    error=str(e),
                )
                competitor_articles_count = 0
                needs_scraping = True
        else:
            needs_scraping = True
    else:
        needs_scraping = True
    
    # ============================================================
    # ÉTAPE 4: Vérifier articles client (client_articles)
    # ============================================================
    needs_client_scraping = False
    
    if profile:
        # client_articles_count a déjà été récupéré dans le gather ci-dessus
        # Vérifier si suffisant (seuil: 5 articles)
        needs_client_scraping = client_articles_count < 5
    else:
        needs_client_scraping = True
    
    # ============================================================
    # DÉCISION: Lancer les workflows manquants ou retourner les données
    # ============================================================
    
    # AVANT de décider de lancer des workflows, vérifier s'il existe un orchestrator "completed" récent
    # Si oui et que les données essentielles sont disponibles, retourner les données directement
    from python_scripts.database.models import WorkflowExecution
    
    completed_orchestrator_stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "audit_orchestrator",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
            WorkflowExecution.is_valid == True,
            WorkflowExecution.was_success == True,  # Seulement les succès complets
        )
        .order_by(desc(WorkflowExecution.end_time))
        .limit(1)
    )
    completed_result = await db.execute(completed_orchestrator_stmt)
    completed_orchestrator = completed_result.scalar_one_or_none()
    
    # Si un orchestrator complet existe et que les données essentielles sont disponibles
    # (profile, competitors, trend_pipeline), retourner les données même s'il manque quelques articles
    # Note: needs_scraping peut être True si aucun concurrent n'est validé, mais on peut quand même retourner les données
    if completed_orchestrator and profile and not needs_analysis and not needs_competitors and not needs_trend_pipeline:
        logger.info(
            "Completed orchestrator found with essential data available, returning audit",
            execution_id=str(completed_orchestrator.execution_id),
            domain=domain,
            missing_scraping=needs_scraping,
            missing_client_scraping=needs_client_scraping,
        )
        # Les données essentielles sont disponibles : construire et retourner la réponse
        return await build_complete_audit_from_database(
            db,
            domain,
            profile,
            competitors_execution,
            trend_execution,
            include_topics=include_topics,
            include_trending=include_trending,
            include_analyses=include_analyses,
            include_temporal=include_temporal,
            include_opportunities=include_opportunities,
            topics_limit=topics_limit,
            trending_limit=trending_limit,
        )
    
    # Si les données essentielles sont disponibles SANS orchestrator complet, retourner aussi les données
    # (cas où l'orchestrator n'existe pas mais toutes les données sont là)
    if profile and not needs_analysis and not needs_competitors and not needs_trend_pipeline:
        logger.info(
            "Essential data available without completed orchestrator, returning audit",
            domain=domain,
            missing_scraping=needs_scraping,
            missing_client_scraping=needs_client_scraping,
        )
        # Les données essentielles sont disponibles : construire et retourner la réponse
        return await build_complete_audit_from_database(
            db,
            domain,
            profile,
            competitors_execution,
            trend_execution,
            include_topics=include_topics,
            include_trending=include_trending,
            include_analyses=include_analyses,
            include_temporal=include_temporal,
            include_opportunities=include_opportunities,
            topics_limit=topics_limit,
            trending_limit=trending_limit,
        )
    
    if (
        needs_analysis
        or needs_competitors
        or needs_scraping
        or needs_client_scraping
        or needs_trend_pipeline
    ):
        # Il manque des données : lancer les workflows nécessaires
        # Vérifier d'abord si un orchestrator existe déjà pour ce domaine (P0-1: Race condition fix)
        existing_orchestrator_stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "audit_orchestrator",
                WorkflowExecution.status.in_(["pending", "running"]),
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,
            )
            .order_by(desc(WorkflowExecution.created_at))
            .limit(1)
        )
        existing_result = await db.execute(existing_orchestrator_stmt)
        existing_orchestrator = existing_result.scalar_one_or_none()
        
        if existing_orchestrator:
            # Un orchestrator existe déjà : retourner celui-ci
            logger.info(
                "Existing orchestrator found, reusing",
                execution_id=str(existing_orchestrator.execution_id),
                domain=domain,
            )
            
            # Construire la liste des étapes depuis input_data
            input_data = existing_orchestrator.input_data or {}
            workflow_steps = []
            step_num = 1
            
            if input_data.get("needs_analysis", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Editorial Analysis",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_competitors", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Competitor Search",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_client_scraping", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Client Site Scraping",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_scraping", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Competitor Scraping",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_trend_pipeline", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Trend Pipeline",
                        status="pending",
                    )
                )
            
            return PendingAuditResponse(
                status="pending",
                execution_id=str(existing_orchestrator.execution_id),
                message="Audit already in progress. Use the execution_id to check status.",
                workflow_steps=workflow_steps,
                data_status=DataStatus(
                    has_profile=not needs_analysis,
                    has_competitors=not needs_competitors,
                    has_client_articles=not needs_client_scraping,
                    has_competitor_articles=not needs_scraping,
                    has_trend_pipeline=not needs_trend_pipeline,
                ),
            )
        
        # Aucun orchestrator existant : créer un nouveau
        orchestrator_execution = await create_workflow_execution(
            db,
            workflow_type="audit_orchestrator",
            input_data={
                "domain": domain,
                "needs_analysis": needs_analysis,
                "needs_competitors": needs_competitors,
                "needs_scraping": needs_scraping,
                "needs_client_scraping": needs_client_scraping,
                "needs_trend_pipeline": needs_trend_pipeline,
            },
            status="running",
        )
        
        # Lancer les workflows manquants en chaîne
        background_tasks.add_task(
            run_missing_workflows_chain,
            domain,
            orchestrator_execution.execution_id,
            needs_analysis=needs_analysis,
            needs_competitors=needs_competitors,
            needs_scraping=needs_scraping,
            needs_client_scraping=needs_client_scraping,
            needs_trend_pipeline=needs_trend_pipeline,
            profile_id=profile.id if profile else None,
        )
        
        # Construire la liste des étapes
        workflow_steps = []
        step_num = 1
        
        if needs_analysis:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Editorial Analysis",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_competitors:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Search",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_client_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Client Site Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_trend_pipeline:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Trend Pipeline",
                    status="pending",
                )
            )
        
        return PendingAuditResponse(
            status="pending",
            execution_id=str(orchestrator_execution.execution_id),
            message="Some data is missing. Launching required workflows...",
            workflow_steps=workflow_steps,
            data_status=DataStatus(
                has_profile=not needs_analysis,
                has_competitors=not needs_competitors,
                has_client_articles=not needs_client_scraping,
                has_competitor_articles=not needs_scraping,
                has_trend_pipeline=not needs_trend_pipeline,
            ),
        )
    
    # ============================================================
    # TOUTES LES DONNÉES SONT DISPONIBLES : Construire la réponse
    # ============================================================
    
    # Récupérer les données complètes depuis la base
    return await build_complete_audit_from_database(
        db,
        domain,
        profile,
        competitors_execution,
        trend_execution,
        include_topics=include_topics,
        include_trending=include_trending,
        include_analyses=include_analyses,
        include_temporal=include_temporal,
        include_opportunities=include_opportunities,
        topics_limit=topics_limit,
        trending_limit=trending_limit,
    )


@router.post(
    "/{domain}/regenerate-summaries",
    response_model=Dict[str, Any],
    summary="Regenerate domain summaries",
    description="""
    Regenerate personalized summaries for all activity domains.
    
    This endpoint:
    1. Generates personalized summaries for each domain based on client articles
    2. Stores summaries in activity_domains.domain_details
    3. Updates topics_count and confidence for each domain
    
    Use this endpoint to:
    - Regenerate summaries after new articles are scraped
    - Update summaries when domain structure changes
    - Force refresh of domain summaries
    """,
    tags=["sites"],
)
async def regenerate_domain_summaries(
    domain: str = Path(
        ...,
        description="Valid domain name (e.g., example.com, innosys.fr)",
        examples=["innosys.fr", "example.com"],
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Regenerate personalized domain summaries and save to profile.
    
    Args:
        domain: Domain name (validated format)
        db: Database session
        
    Returns:
        Dictionary with regeneration results
        
    Raises:
        HTTPException: 422 if domain format is invalid, 404 if profile not found
    """
    # Validation du domaine
    if not DOMAIN_REGEX.match(domain):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid domain format: {domain}. Expected format: example.com",
        )
    
    # Get site profile
    profile = await get_site_profile_by_domain(db, domain)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )
    
    # Get trend execution if available
    trend_execution = await _check_trend_pipeline(db, domain)
    
    # Generate and save summaries
    try:
        await _save_domain_summaries_to_profile(
            db,
            profile,
            trend_execution=trend_execution,
        )
        
        # Get updated activity_domains to return
        activity_domains = _safe_json_field(profile.activity_domains) or {}
        domain_details = activity_domains.get("domain_details", {})
        
        return {
            "status": "success",
            "message": "Domain summaries regenerated successfully",
            "domain": domain,
            "domains_updated": len(domain_details),
            "domain_details": domain_details,
        }
    except Exception as e:
        logger.error(
            "Error regenerating domain summaries",
            domain=domain,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate summaries: {str(e)}",
        )


@router.get(
    "/{domain}/audit/status/{execution_id}",
    response_model=AuditStatusResponse,
    summary="Get audit execution status",
    description="""
    Récupère le statut global de l'audit avec tous les workflows enfants.
    
    Cette route permet de suivre la progression de l'audit en temps réel,
    avec le statut détaillé de chaque étape et une progression globale.
    
    Utilisez cette route pour poller le statut de l'audit après avoir reçu
    un `PendingAuditResponse` avec un `execution_id`.
    
    Note: Si l'audit est déjà complété et que toutes les données sont disponibles,
    utilisez directement GET /{domain}/audit pour obtenir les données complètes.
    """,
    tags=["sites"],
)
async def get_audit_status(
    domain: str,
    execution_id: str,  # Accepter string pour gérer les cas spéciaux
    db: AsyncSession = Depends(get_db),
) -> AuditStatusResponse:
    """
    Récupère le statut global de l'audit.
    
    Args:
        domain: Domaine analysé
        execution_id: ID de l'orchestrator execution (UUID ou "already-completed")
        db: Session de base de données
        
    Returns:
        Statut global de l'audit avec détails de chaque étape
        
    Raises:
        HTTPException: 404 si l'orchestrator n'est pas trouvé, 422 si execution_id invalide
    """
    # Gérer le cas spécial "already-completed"
    if execution_id == "already-completed":
        # Chercher l'orchestrator "completed" le plus récent pour ce domaine
        from python_scripts.database.models import WorkflowExecution
        
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "audit_orchestrator",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,
                WorkflowExecution.was_success == True,
            )
            .order_by(desc(WorkflowExecution.end_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        orchestrator = result.scalar_one_or_none()
        
        if not orchestrator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No completed orchestrator found for domain: {domain}",
            )
        
        execution_id_uuid = orchestrator.execution_id
    else:
        # Valider que c'est un UUID valide
        try:
            execution_id_uuid = UUID(execution_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid execution_id format: {execution_id}. Expected UUID or 'already-completed'",
            )
    
    status_response = await _get_audit_status(db, execution_id_uuid, domain)
    
    # Log pour déboguer le polling continu
    if status_response.overall_status in ("completed", "failed"):
        logger.debug(
            "Audit status requested for completed/failed audit",
            execution_id=str(execution_id_uuid),
            domain=domain,
            overall_status=status_response.overall_status,
            overall_progress=status_response.overall_progress,
        )
    
    return status_response

