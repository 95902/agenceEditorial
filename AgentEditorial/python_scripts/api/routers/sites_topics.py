"""API router for topics endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import (
    CompetitorDetail,
    DomainTopicsResponse,
    SourceDetail,
    TopicDetail,
    TopicDetailsResponse,
    TrendDetail,
)
from python_scripts.api.services.audit_service import _get_cluster_by_topic_id
from python_scripts.api.utils.sites_utils import (
    _calculate_read_time,
    _calculate_trend_delta,
    _count_articles_for_domain,
    _determine_trend,
    _extract_key_points_from_outline,
    _extract_topic_id_from_slug,
    _generate_predictions,
    _normalize_site_client,
    _slugify_topic_id,
    _transform_opportunities_to_angles,
)
from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis
from python_scripts.database.crud_llm_results import (
    get_article_recommendations_by_topic_cluster,
    get_trend_analyses_by_topic_cluster,
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.crud_temporal_metrics import get_temporal_metrics_by_topic_cluster
from python_scripts.database.models import (
    ClientArticle,
    CompetitorArticle,
    TrendPipelineExecution,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sites", tags=["sites"])


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
) -> TopicDetailsResponse:
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


@router.get(
    "/topics",
    response_model=DomainTopicsResponse,
    summary="Get topics by domain",
    description="""
    Get topics for a specific activity domain.
    
    Example:
        GET /api/v1/sites/topics?domain=Cloud%20Infrastructure%20Management&site_client=innosys.fr
    """,
    responses={
        200: {
            "description": "Topics retrieved successfully",
        },
        404: {
            "description": "Site profile, domain, or trend pipeline not found",
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

