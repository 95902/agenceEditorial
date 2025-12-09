"""Main article enrichment service."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.analysis.article_enrichment.config import ArticleEnrichmentConfig
from python_scripts.analysis.article_enrichment.llm_enricher import ArticleLLMEnricher
from python_scripts.database.crud_profiles import get_client_context_for_enrichment
from python_scripts.database.models import (
    ArticleRecommendation,
    EditorialGap,
    TopicCluster,
    TopicTemporalMetrics,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleEnricher:
    """Main article enrichment service."""
    
    def __init__(self, config: Optional[ArticleEnrichmentConfig] = None):
        """
        Initialize the article enricher.
        
        Args:
            config: Article enrichment configuration
        """
        self.config = config or ArticleEnrichmentConfig.default()
        self.llm_enricher = ArticleLLMEnricher(config)
    
    async def enrich_article(
        self,
        db_session: AsyncSession,
        article_id: int,
        client_domain: str,
    ) -> Dict[str, Any]:
        """
        Enrich a single article recommendation.
        
        Args:
            db_session: Database session
            article_id: ArticleRecommendation ID
            client_domain: Client domain (e.g., "innosys.fr")
            
        Returns:
            Enriched article data
        """
        # Get article recommendation
        result = await db_session.execute(
            select(ArticleRecommendation).where(
                ArticleRecommendation.id == article_id,
                ArticleRecommendation.is_valid == True,  # noqa: E712
            )
        )
        article = result.scalar_one_or_none()
        
        if not article:
            raise ValueError(f"Article recommendation {article_id} not found")
        
        # Get client context
        client_context = await get_client_context_for_enrichment(db_session, client_domain)
        if not client_context:
            logger.warning("Client context not found", domain=client_domain)
            client_context = {}
        
        # Get statistics from topic cluster and related data
        statistics = await self._get_topic_statistics(
            db_session,
            article.topic_cluster_id,
        )
        
        # Enrich using LLM
        enriched = await self.llm_enricher.enrich_complete(
            title=article.title,
            hook=article.hook,
            outline=article.outline,
            effort_level=article.effort_level,
            differentiation_score=article.differentiation_score,
            client_context=client_context,
            statistics=statistics,
        )
        
        return {
            "article_id": article_id,
            "original": {
                "title": article.title,
                "hook": article.hook,
                "outline": article.outline,
                "effort_level": article.effort_level,
                "differentiation_score": article.differentiation_score,
            },
            "enriched": enriched,
            "client_context_used": client_context,
            "statistics_used": statistics,
        }
    
    async def enrich_articles_batch(
        self,
        db_session: AsyncSession,
        article_ids: List[int],
        client_domain: str,
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple article recommendations.
        
        Args:
            db_session: Database session
            article_ids: List of ArticleRecommendation IDs
            client_domain: Client domain
            
        Returns:
            List of enriched article data
        """
        results = []
        
        # Get client context once (shared for all articles)
        client_context = await get_client_context_for_enrichment(db_session, client_domain)
        if not client_context:
            logger.warning("Client context not found", domain=client_domain)
            client_context = {}
        
        # Get all articles
        result = await db_session.execute(
            select(ArticleRecommendation).where(
                ArticleRecommendation.id.in_(article_ids),
                ArticleRecommendation.is_valid == True,  # noqa: E712
            )
        )
        articles = result.scalars().all()
        
        # Enrich each article
        for article in articles:
            try:
                # Get statistics for this article's topic
                statistics = await self._get_topic_statistics(
                    db_session,
                    article.topic_cluster_id,
                )
                
                # Enrich using LLM
                enriched = await self.llm_enricher.enrich_complete(
                    title=article.title,
                    hook=article.hook,
                    outline=article.outline,
                    effort_level=article.effort_level,
                    differentiation_score=article.differentiation_score,
                    client_context=client_context,
                    statistics=statistics,
                )
                
                results.append({
                    "article_id": article.id,
                    "original": {
                        "title": article.title,
                        "hook": article.hook,
                        "outline": article.outline,
                        "effort_level": article.effort_level,
                        "differentiation_score": article.differentiation_score,
                    },
                    "enriched": enriched,
                    "statistics_used": statistics,
                })
                
            except Exception as e:
                logger.error(
                    "Failed to enrich article",
                    article_id=article.id,
                    error=str(e),
                )
                results.append({
                    "article_id": article.id,
                    "error": str(e),
                })
        
        return results
    
    async def _get_topic_statistics(
        self,
        db_session: AsyncSession,
        topic_cluster_id: int,
    ) -> Dict[str, Any]:
        """
        Get statistics for a topic cluster.
        
        Args:
            db_session: Database session
            topic_cluster_id: Topic cluster ID
            
        Returns:
            Dictionary with statistics (volume, velocity, priority, etc.)
        """
        # Get topic cluster
        result = await db_session.execute(
            select(TopicCluster).where(
                TopicCluster.id == topic_cluster_id,
                TopicCluster.is_valid == True,  # noqa: E712
            )
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            return {
                "competitor_volume": 0,
                "velocity": 0.0,
                "velocity_trend": "stable",
                "priority_score": 0.0,
                "coverage_gap": 0.0,
                "source_diversity": 0,
            }
        
        # Get latest temporal metrics
        result = await db_session.execute(
            select(TopicTemporalMetrics)
            .where(
                TopicTemporalMetrics.topic_cluster_id == topic_cluster_id,
                TopicTemporalMetrics.is_valid == True,  # noqa: E712
            )
            .order_by(TopicTemporalMetrics.created_at.desc())
            .limit(1)
        )
        temporal_metric = result.scalar_one_or_none()
        
        # Get editorial gap if exists
        result = await db_session.execute(
            select(EditorialGap).where(
                EditorialGap.topic_cluster_id == topic_cluster_id,
                EditorialGap.is_valid == True,  # noqa: E712
            )
            .order_by(EditorialGap.created_at.desc())
            .limit(1)
        )
        gap = result.scalar_one_or_none()
        
        # Build statistics dictionary
        statistics = {
            "competitor_volume": cluster.article_count or 0,
            "velocity": float(temporal_metric.velocity) if temporal_metric and temporal_metric.velocity else 0.0,
            "velocity_trend": "increasing" if temporal_metric and temporal_metric.velocity and float(temporal_metric.velocity) > 1.2 else "stable",
            "priority_score": float(gap.priority_score) if gap else 0.0,
            "coverage_gap": float(gap.coverage_score) if gap else 0.0,
            "source_diversity": temporal_metric.source_diversity if temporal_metric else 0,
            "freshness_ratio": float(temporal_metric.freshness_ratio) if temporal_metric and temporal_metric.freshness_ratio else 0.0,
        }
        
        return statistics



