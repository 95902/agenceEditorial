"""Script pour nettoyer la base de données."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    GeneratedArticle,
    GeneratedArticleImage,
    GeneratedArticleVersion,
    ArticleLearningData,
    ClientArticle,
    CompetitorArticle,
    TrendPipelineExecution,
    TopicCluster,
    TopicOutlier,
    WorkflowExecution,
    CrawlCache,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def clean_generated_articles(
    db: AsyncSession,
    older_than_days: Optional[int] = None,
    status_filter: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Nettoie les articles générés.
    
    Args:
        db: Session de base de données
        older_than_days: Supprimer uniquement les articles plus anciens que X jours
        status_filter: Filtrer par statut (ex: "failed", "initialized")
        dry_run: Si True, ne fait que compter sans supprimer
        
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    conditions = [GeneratedArticle.is_valid == True]  # noqa: E712
    
    if older_than_days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        conditions.append(GeneratedArticle.created_at < cutoff_date)
    
    if status_filter:
        conditions.append(GeneratedArticle.status == status_filter)
    
    stmt = select(GeneratedArticle).where(*conditions)
    result = await db.execute(stmt)
    articles = list(result.scalars().all())
    
    count = len(articles)
    
    if not dry_run and count > 0:
        for article in articles:
            article.is_valid = False
        await db.commit()
        logger.info(f"Soft deleted {count} generated articles")
    
    return {
        "articles_found": count,
        "articles_deleted": count if not dry_run else 0,
    }


async def clean_generated_article_images(
    db: AsyncSession,
    older_than_days: Optional[int] = None,
    without_article: bool = True,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Nettoie les images générées.
    
    Args:
        db: Session de base de données
        older_than_days: Supprimer uniquement les images plus anciennes que X jours
        without_article: Supprimer les images sans article associé valide
        dry_run: Si True, ne fait que compter sans supprimer
        
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    conditions = []
    
    if older_than_days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        conditions.append(GeneratedArticleImage.created_at < cutoff_date)
    
    if without_article:
        # Trouver les images dont l'article n'existe pas ou est invalide
        stmt = (
            select(GeneratedArticleImage)
            .outerjoin(GeneratedArticle, GeneratedArticleImage.article_id == GeneratedArticle.id)
            .where(
                (GeneratedArticle.id.is_(None)) | (GeneratedArticle.is_valid == False)  # noqa: E712
            )
        )
        if conditions:
            for cond in conditions:
                stmt = stmt.where(cond)
    else:
        stmt = select(GeneratedArticleImage)
        if conditions:
            for cond in conditions:
                stmt = stmt.where(cond)
    
    result = await db.execute(stmt)
    images = list(result.scalars().all())
    
    count = len(images)
    
    if not dry_run and count > 0:
        for image in images:
            await db.delete(image)
        await db.commit()
        logger.info(f"Deleted {count} generated article images")
    
    return {
        "images_found": count,
        "images_deleted": count if not dry_run else 0,
    }


async def clean_failed_workflows(
    db: AsyncSession,
    older_than_days: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Nettoie les exécutions de workflow en échec.
    
    Args:
        db: Session de base de données
        older_than_days: Supprimer uniquement les exécutions plus anciennes que X jours
        dry_run: Si True, ne fait que compter sans supprimer
        
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    conditions = [
        WorkflowExecution.is_valid == True,  # noqa: E712
        WorkflowExecution.status.in_(["failed", "error", "cancelled"]),
    ]
    
    if older_than_days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        conditions.append(WorkflowExecution.created_at < cutoff_date)
    
    stmt = select(WorkflowExecution).where(*conditions)
    result = await db.execute(stmt)
    executions = list(result.scalars().all())
    
    count = len(executions)
    
    if not dry_run and count > 0:
        for execution in executions:
            execution.is_valid = False
        await db.commit()
        logger.info(f"Soft deleted {count} failed workflow executions")
    
    return {
        "executions_found": count,
        "executions_deleted": count if not dry_run else 0,
    }


async def clean_expired_crawl_cache(
    db: AsyncSession,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Nettoie le cache de crawl expiré.
    
    Args:
        db: Session de base de données
        dry_run: Si True, ne fait que compter sans supprimer
        
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    now = datetime.now(timezone.utc)
    
    stmt = select(CrawlCache).where(CrawlCache.expires_at < now)
    result = await db.execute(stmt)
    expired = list(result.scalars().all())
    
    count = len(expired)
    
    if not dry_run and count > 0:
        for entry in expired:
            await db.delete(entry)
        await db.commit()
        logger.info(f"Deleted {count} expired crawl cache entries")
    
    return {
        "cache_entries_found": count,
        "cache_entries_deleted": count if not dry_run else 0,
    }


async def clean_old_trend_pipeline_executions(
    db: AsyncSession,
    older_than_days: int = 30,
    keep_latest: int = 5,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Nettoie les anciennes exécutions de trend pipeline.
    
    Args:
        db: Session de base de données
        older_than_days: Supprimer les exécutions plus anciennes que X jours
        keep_latest: Garder les N dernières exécutions même si elles sont anciennes
        dry_run: Si True, ne fait que compter sans supprimer
        
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    # Récupérer les exécutions triées par date
    stmt = (
        select(TrendPipelineExecution)
        .where(TrendPipelineExecution.is_valid == True)  # noqa: E712
        .order_by(TrendPipelineExecution.start_time.desc())
    )
    result = await db.execute(stmt)
    all_executions = list(result.scalars().all())
    
    if len(all_executions) <= keep_latest:
        return {
            "executions_found": 0,
            "executions_deleted": 0,
            "message": f"Only {len(all_executions)} executions found, keeping all",
        }
    
    # Garder les N dernières
    executions_to_keep = all_executions[:keep_latest]
    executions_to_check = all_executions[keep_latest:]
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    executions_to_delete = [
        e for e in executions_to_check
        if e.start_time and e.start_time < cutoff_date
    ]
    
    count = len(executions_to_delete)
    
    if not dry_run and count > 0:
        for execution in executions_to_delete:
            execution.is_valid = False
        await db.commit()
        logger.info(f"Soft deleted {count} old trend pipeline executions")
    
    return {
        "executions_found": count,
        "executions_deleted": count if not dry_run else 0,
        "executions_kept": len(executions_to_keep),
    }


async def get_database_stats(db: AsyncSession) -> Dict[str, int]:
    """Récupère les statistiques de la base de données."""
    stats = {}
    
    # Articles générés
    stmt = select(func.count(GeneratedArticle.id)).where(GeneratedArticle.is_valid == True)  # noqa: E712
    result = await db.execute(stmt)
    stats["generated_articles"] = result.scalar() or 0
    
    # Images générées
    stmt = select(func.count(GeneratedArticleImage.id))
    result = await db.execute(stmt)
    stats["generated_images"] = result.scalar() or 0
    
    # Articles clients
    stmt = select(func.count(ClientArticle.id)).where(ClientArticle.is_valid == True)  # noqa: E712
    result = await db.execute(stmt)
    stats["client_articles"] = result.scalar() or 0
    
    # Articles concurrents
    stmt = select(func.count(CompetitorArticle.id)).where(CompetitorArticle.is_valid == True)  # noqa: E712
    result = await db.execute(stmt)
    stats["competitor_articles"] = result.scalar() or 0
    
    # Exécutions de pipeline
    stmt = select(func.count(TrendPipelineExecution.id)).where(TrendPipelineExecution.is_valid == True)  # noqa: E712
    result = await db.execute(stmt)
    stats["trend_pipeline_executions"] = result.scalar() or 0
    
    # Cache de crawl
    stmt = select(func.count(CrawlCache.id))
    result = await db.execute(stmt)
    stats["crawl_cache_entries"] = result.scalar() or 0
    
    return stats


async def main():
    """Fonction principale de nettoyage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nettoyer la base de données")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode simulation (ne supprime rien, affiche seulement les statistiques)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Nettoyer tout (articles, images, workflows, cache)",
    )
    parser.add_argument(
        "--articles",
        action="store_true",
        help="Nettoyer les articles générés",
    )
    parser.add_argument(
        "--articles-failed",
        action="store_true",
        help="Nettoyer uniquement les articles en échec",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="Nettoyer les images générées",
    )
    parser.add_argument(
        "--workflows",
        action="store_true",
        help="Nettoyer les workflows en échec",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Nettoyer le cache de crawl expiré",
    )
    parser.add_argument(
        "--trend-pipelines",
        action="store_true",
        help="Nettoyer les anciennes exécutions de trend pipeline",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        help="Supprimer uniquement les éléments plus anciens que X jours",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Afficher uniquement les statistiques (sans nettoyer)",
    )
    
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as db:
        # Afficher les statistiques
        print("\n" + "=" * 80)
        print("📊 STATISTIQUES DE LA BASE DE DONNÉES")
        print("=" * 80)
        stats = await get_database_stats(db)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print("=" * 80 + "\n")
        
        if args.stats:
            return
        
        if args.dry_run:
            print("🔍 MODE SIMULATION (dry-run) - Aucune suppression ne sera effectuée\n")
        
        results = {}
        
        # Nettoyage selon les options
        if args.all or args.articles or args.articles_failed:
            print("🧹 Nettoyage des articles générés...")
            status_filter = "failed" if args.articles_failed else None
            results["articles"] = await clean_generated_articles(
                db,
                older_than_days=args.older_than_days,
                status_filter=status_filter,
                dry_run=args.dry_run,
            )
            print(f"  ✅ Articles trouvés: {results['articles']['articles_found']}")
            if not args.dry_run:
                print(f"  🗑️  Articles supprimés: {results['articles']['articles_deleted']}")
            print()
        
        if args.all or args.images:
            print("🖼️  Nettoyage des images générées...")
            results["images"] = await clean_generated_article_images(
                db,
                older_than_days=args.older_than_days,
                without_article=True,
                dry_run=args.dry_run,
            )
            print(f"  ✅ Images trouvées: {results['images']['images_found']}")
            if not args.dry_run:
                print(f"  🗑️  Images supprimées: {results['images']['images_deleted']}")
            print()
        
        if args.all or args.workflows:
            print("⚙️  Nettoyage des workflows en échec...")
            results["workflows"] = await clean_failed_workflows(
                db,
                older_than_days=args.older_than_days,
                dry_run=args.dry_run,
            )
            print(f"  ✅ Workflows trouvés: {results['workflows']['executions_found']}")
            if not args.dry_run:
                print(f"  🗑️  Workflows supprimés: {results['workflows']['executions_deleted']}")
            print()
        
        if args.all or args.cache:
            print("🗄️  Nettoyage du cache de crawl expiré...")
            results["cache"] = await clean_expired_crawl_cache(db, dry_run=args.dry_run)
            print(f"  ✅ Entrées de cache trouvées: {results['cache']['cache_entries_found']}")
            if not args.dry_run:
                print(f"  🗑️  Entrées supprimées: {results['cache']['cache_entries_deleted']}")
            print()
        
        if args.all or args.trend_pipelines:
            print("📈 Nettoyage des anciennes exécutions de trend pipeline...")
            results["trend_pipelines"] = await clean_old_trend_pipeline_executions(
                db,
                older_than_days=args.older_than_days or 30,
                keep_latest=5,
                dry_run=args.dry_run,
            )
            print(f"  ✅ Exécutions trouvées: {results['trend_pipelines']['executions_found']}")
            if not args.dry_run:
                print(f"  🗑️  Exécutions supprimées: {results['trend_pipelines']['executions_deleted']}")
            print()
        
        # Résumé
        if results:
            print("=" * 80)
            print("📋 RÉSUMÉ DU NETTOYAGE")
            print("=" * 80)
            total_deleted = sum(
                r.get("articles_deleted", 0) +
                r.get("images_deleted", 0) +
                r.get("executions_deleted", 0) +
                r.get("cache_entries_deleted", 0)
                for r in results.values()
            )
            if args.dry_run:
                print(f"  🔍 Total d'éléments qui seraient supprimés: {total_deleted}")
                print("\n  ⚠️  Pour effectuer la suppression, relancez sans --dry-run")
            else:
                print(f"  ✅ Total d'éléments supprimés: {total_deleted}")
            print("=" * 80 + "\n")
        else:
            print("ℹ️  Aucune option de nettoyage spécifiée.")
            print("   Utilisez --help pour voir les options disponibles.\n")


if __name__ == "__main__":
    asyncio.run(main())




