"""Script pour vider toutes les tables de la base de données."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from python_scripts.config.settings import settings
from python_scripts.database.models import (
    AuditLog,
    BertopicAnalysis,
    ClientArticle,
    CompetitorArticle,
    ContentRoadmap,
    CrawlCache,
    ClientCoverageAnalysis,
    ClientStrength,
    DiscoveryLog,
    EditorialGap,
    EditorialTrend,
    ErrorLog,
    ArticleRecommendation,
    PerformanceMetric,
    ScrapingPermission,
    SiteAnalysisResult,
    SiteDiscoveryProfile,
    SiteProfile,
    TopicCluster,
    TopicOutlier,
    TopicTemporalMetrics,
    TrendAnalysis,
    TrendPipelineExecution,
    UrlDiscoveryScore,
    WeakSignalAnalysis,
    WorkflowExecution,
)


async def clear_database():
    """Vide toutes les tables de la base de données."""
    # Créer une connexion async
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
    )

    async with engine.begin() as conn:
        print("🚀 Début du vidage de la base de données...")
        
        # Désactiver temporairement les contraintes de clés étrangères
        await conn.execute(text("SET session_replication_role = 'replica';"))
        
        # Liste de toutes les tables dans l'ordre inverse des dépendances
        # (on commence par les tables qui n'ont pas de dépendances)
        tables = [
            "content_roadmap",
            "weak_signals_analysis",
            "article_recommendations",
            "trend_analysis",
            "client_strengths",
            "editorial_gaps",
            "client_coverage_analysis",
            "topic_temporal_metrics",
            "topic_outliers",
            "topic_clusters",
            "bertopic_analysis",
            "editorial_trends",
            "url_discovery_scores",
            "discovery_logs",
            "site_discovery_profiles",
            "error_logs",
            "audit_log",
            "performance_metrics",
            "site_analysis_results",
            "client_articles",
            "competitor_articles",
            "crawl_cache",
            "scraping_permissions",
            "trend_pipeline_executions",
            "workflow_executions",
            "site_profiles",
        ]
        
        for table in tables:
            try:
                result = await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                print(f"✅ Table '{table}' vidée")
            except Exception as e:
                print(f"⚠️  Erreur lors du vidage de '{table}': {e}")
        
        # Réactiver les contraintes
        await conn.execute(text("SET session_replication_role = 'origin';"))
        
        print("\n✨ Base de données vidée avec succès!")
        print(f"📊 {len(tables)} tables traitées")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(clear_database())



