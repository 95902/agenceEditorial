"""Script pour vider toutes les tables de la base de données et supprimer les images."""

import asyncio
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from python_scripts.config.settings import settings
from python_scripts.database.models import (
    AuditLog,
    ClientArticle,
    CompetitorArticle,
    ContentRoadmap,
    CrawlCache,
    ClientCoverageAnalysis,
    ClientStrength,
    DiscoveryLog,
    EditorialGap,
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
    GeneratedArticle,
    GeneratedArticleImage,
    GeneratedArticleVersion,
    GeneratedImage,
)


async def clear_database():
    """Vide toutes les tables de la base de données et supprime les images."""
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
            "url_discovery_scores",
            "discovery_logs",
            "site_discovery_profiles",
            "error_logs",
            "audit_log",
            "performance_metrics",
            "site_analysis_results",
            "generated_article_versions",
            "generated_article_images",
            "generated_articles",
            "generated_images",
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
    
    # Supprimer les images générées
    print("\n🖼️  Suppression des images générées...")
    images_dir = Path(__file__).parent.parent / "outputs" / "articles" / "images"
    
    if images_dir.exists():
        try:
            # Compter les fichiers avant suppression
            image_files = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.jpeg"))
            count = len(image_files)
            
            # Supprimer tous les fichiers d'images
            for image_file in image_files:
                try:
                    image_file.unlink()
                except Exception as e:
                    print(f"⚠️  Erreur lors de la suppression de '{image_file.name}': {e}")
            
            print(f"✅ {count} image(s) supprimée(s) du répertoire '{images_dir}'")
        except Exception as e:
            print(f"⚠️  Erreur lors de la suppression des images: {e}")
    else:
        print(f"ℹ️  Le répertoire '{images_dir}' n'existe pas")
    
    print("\n🎉 Nettoyage terminé avec succès!")


if __name__ == "__main__":
    asyncio.run(clear_database())






