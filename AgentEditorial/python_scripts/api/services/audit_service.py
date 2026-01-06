"""Audit service for sites API."""

import asyncio
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.schemas.responses import (
    AuditIssue,
    AuditStatusResponse,
    DataStatus,
    DomainDetail,
    DomainMetrics,
    EditorialOpportunity,
    EditorialOpportunityDetail,
    IssueCode,
    IssueSeverity,
    SiteAuditResponse,
    SaturatedAngle,
    TemporalInsight,
    TimeWindow,
    TopicSummary,
    TrendingTopic,
    TrendAnalysisDetail,
    WorkflowStepDetail,
)
from python_scripts.api.utils.sites_utils import (
    _calculate_article_format,
    _calculate_read_time,
    _calculate_trend_delta,
    _count_articles_for_domain,
    _determine_trend,
    _extract_audience_sectors,
    _extract_key_points_from_outline,
    _extract_topic_id_from_slug,
    _generate_predictions,
    _map_language_level_to_audience_level,
    _map_language_level_to_vocabulary,
    _normalize_site_client,
    _safe_json_field,
    _slugify,
    _slugify_topic_id,
    _transform_opportunities_to_angles,
)
from python_scripts.database.crud_clusters import (
    get_topic_cluster_by_topic_id,
    get_topic_clusters_by_analysis,
)
from python_scripts.database.crud_client_articles import (
    count_client_articles,
    list_client_articles,
)
from python_scripts.database.crud_articles import count_competitor_articles
from python_scripts.database.crud_executions import (
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.database.crud_llm_results import (
    get_article_recommendations_by_analysis,
    get_article_recommendations_by_topic_cluster,
    get_trend_analyses_by_analysis,
    get_trend_analyses_by_topic_cluster,
)
from python_scripts.database.crud_profiles import (
    get_site_profile_by_domain,
    update_site_profile,
)
from python_scripts.database.crud_temporal_metrics import get_temporal_metrics_by_topic_cluster
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    ArticleRecommendation,
    ClientArticle,
    CompetitorArticle,
    SiteProfile,
    TopicCluster,
    TrendAnalysis,
    TrendPipelineExecution,
    WorkflowExecution,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

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
    total_clusters = len(clusters)

    logger.debug(
        f"Counting topics for domain '{domain_label}': {total_clusters} clusters to check",
        domain=domain_label,
        total_clusters=total_clusters,
    )

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
            # Amélioration: utiliser mots-clés plus flexibles (>2 chars au lieu de >3)
            domain_keywords = set(domain_label.lower().split())
            domain_keywords = {kw for kw in domain_keywords if len(kw) > 2}  # Plus souple

            label_lower = cluster.label.lower() if cluster.label else ""
            top_terms = cluster.top_terms.get("terms", []) if cluster.top_terms else []
            top_terms_str = " ".join(str(t).lower() for t in top_terms[:15])

            # Amélioration: vérifier similarité partielle (contain) plutôt qu'égalité exacte
            cluster_matches = any(
                keyword in label_lower or keyword in top_terms_str
                for keyword in domain_keywords
            )

            # Nouveau: si le domaine est "cloud computing" et le cluster parle de "cloud", c'est pertinent
            # Vérifier les mots individuels du domaine dans les termes du cluster
            if not cluster_matches:
                for keyword in domain_keywords:
                    if any(keyword in term.lower() for term in top_terms[:20] if isinstance(term, str)):
                        cluster_matches = True
                        break

            # Fallback: vérifier si des articles concurrents matchent ce domaine
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

    logger.debug(
        f"Topic count for domain '{domain_label}': {relevant_count}/{total_clusters} clusters matched",
        domain=domain_label,
        relevant_count=relevant_count,
        total_clusters=total_clusters,
    )

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
def detect_audit_issues(
    domains_list: List[Any],
    competitors: List[Dict[str, Any]],
    trend_execution: Optional[Any],
    client_articles: List[Any],
) -> List[Any]:
    """
    Détecte les problèmes dans les données d'audit et génère des issues structurées.

    Args:
        domains_list: Liste des domaines d'activité avec confidence, topics_count, etc.
        competitors: Liste des concurrents
        trend_execution: Exécution du pipeline de tendances (peut être None)
        client_articles: Articles du client

    Returns:
        Liste d'AuditIssue détectant les problèmes
    """
    from python_scripts.api.schemas.responses import (
        AuditIssue,
        IssueCode,
        IssueSeverity,
    )

    issues = []

    # 1. Détecter confiance faible (< 15%)
    low_confidence_domains = [d for d in domains_list if d.confidence < 15]
    if low_confidence_domains:
        domain_names = [d.label for d in low_confidence_domains]
        issues.append(
            AuditIssue(
                code=IssueCode.LOW_CONFIDENCE,
                severity=IssueSeverity.CRITICAL,
                message=f"{len(low_confidence_domains)} domaine(s) avec confiance < 15%",
                suggestion="Vérifier la qualité du scraping et l'extraction de contenu. Implémenter Trafilatura pour éviter la pollution boilerplate.",
                context={"affected_domains": domain_names},
            )
        )

    # 2. Détecter keywords dupliqués (pollution boilerplate)
    # Extraire les mots-clés des articles client pour détecter la duplication
    keyword_sets = {}
    for article in client_articles:
        # Si l'article a des métadonnées keywords
        if hasattr(article, "metadata") and article.metadata:
            kw = article.metadata.get("keywords", [])
            if kw:
                domain_label = article.metadata.get("domain", "unknown")
                if domain_label not in keyword_sets:
                    keyword_sets[domain_label] = set()
                keyword_sets[domain_label].update(kw[:5])  # Top 5 keywords

    # Comparer les sets de keywords entre domaines
    if len(keyword_sets) >= 2:
        domain_pairs_similar = []
        domain_names = list(keyword_sets.keys())
        for i in range(len(domain_names)):
            for j in range(i + 1, len(domain_names)):
                d1, d2 = domain_names[i], domain_names[j]
                intersection = keyword_sets[d1] & keyword_sets[d2]
                # Si > 60% de similitude dans les keywords
                similarity = len(intersection) / min(len(keyword_sets[d1]), len(keyword_sets[d2]))
                if similarity > 0.6:
                    domain_pairs_similar.append((d1, d2))

        if domain_pairs_similar:
            issues.append(
                AuditIssue(
                    code=IssueCode.DUPLICATE_KEYWORDS,
                    severity=IssueSeverity.CRITICAL,
                    message=f"{len(domain_pairs_similar)} paire(s) de domaines avec keywords identiques (>60% similitude)",
                    suggestion="Pollution boilerplate détectée. Activer Trafilatura pour nettoyer le contenu extrait.",
                    context={"similar_pairs": [f"{p[0]} ↔ {p[1]}" for p in domain_pairs_similar]},
                )
            )

    # 3. Détecter absence de concurrents
    if not competitors or len(competitors) == 0:
        issues.append(
            AuditIssue(
                code=IssueCode.NO_COMPETITORS,
                severity=IssueSeverity.WARNING,
                message="Aucun concurrent identifié",
                suggestion="Lancer la recherche de concurrents ou ajouter manuellement des concurrents.",
                context={},
            )
        )

    # 4. Détecter articles insuffisants
    if len(client_articles) < 5:
        issues.append(
            AuditIssue(
                code=IssueCode.INSUFFICIENT_ARTICLES,
                severity=IssueSeverity.WARNING,
                message=f"Seulement {len(client_articles)} article(s) analysé(s) (recommandé: 5+)",
                suggestion="Lancer le scraping des articles client pour améliorer l'analyse.",
                context={"articles_count": len(client_articles)},
            )
        )

    # 5. Détecter incohérence topics_count
    # Si topics_count = 0 pour tous les domaines alors que trend_execution existe
    if trend_execution:
        all_zero_topics = all(d.topics_count == 0 for d in domains_list)
        if all_zero_topics and len(domains_list) > 0:
            issues.append(
                AuditIssue(
                    code=IssueCode.TOPICS_COUNT_MISMATCH,
                    severity=IssueSeverity.WARNING,
                    message="Tous les domaines ont topics_count=0 malgré un pipeline de tendances complété",
                    suggestion="Vérifier la logique de mapping entre topics et domaines dans _count_topics_for_domain().",
                    context={},
                )
            )

    # 6. Détecter pipeline de tendances manquant
    if not trend_execution:
        issues.append(
            AuditIssue(
                code=IssueCode.MISSING_OPPORTUNITIES,
                severity=IssueSeverity.INFO,
                message="Pipeline de tendances non exécuté",
                suggestion="Lancer le pipeline de tendances pour enrichir l'analyse avec opportunities et saturated_angles.",
                context={},
            )
        )

    return issues
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

    # 8. Détection des problèmes (issues)
    issues = detect_audit_issues(
        domains_list=domains_list,
        competitors=competitors,
        trend_execution=trend_execution,
        client_articles=client_articles,
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
        issues=issues,
    )
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
