#!/usr/bin/env python3
"""Script pour indexer rétroactivement les articles existants dans Qdrant."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import CompetitorArticle
from python_scripts.database.crud_articles import update_qdrant_point_id
from python_scripts.vectorstore.qdrant_client import qdrant_client
from python_scripts.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def index_existing_articles(
    domain: str | None = None,
    batch_size: int = 100,
) -> dict[str, int]:
    """
    Indexe les articles existants qui n'ont pas encore de qdrant_point_id.
    
    Args:
        domain: Domaine spécifique (optionnel, None = tous les domaines)
        batch_size: Nombre d'articles à traiter par batch
        
    Returns:
        Statistiques (indexed, duplicates, errors)
    """
    stats = {"indexed": 0, "duplicates": 0, "errors": 0, "total": 0}
    
    async with AsyncSessionLocal() as db_session:
        # Requête pour trouver les articles sans qdrant_point_id
        query = select(CompetitorArticle).where(
            and_(
                CompetitorArticle.is_valid == True,  # noqa: E712
                CompetitorArticle.qdrant_point_id.is_(None),
            )
        )
        
        if domain:
            query = query.where(CompetitorArticle.domain == domain)
        
        result = await db_session.execute(query)
        articles = list(result.scalars().all())
        stats["total"] = len(articles)
        
        logger.info(
            "Found articles to index",
            total=len(articles),
            domain=domain or "all",
        )
        
        if len(articles) == 0:
            logger.info("No articles to index")
            return stats
        
        for i, article in enumerate(articles, 1):
            try:
                # Indexer l'article
                qdrant_point_id = qdrant_client.index_article(
                    article_id=article.id,
                    domain=article.domain,
                    title=article.title,
                    content_text=article.content_text,
                    url=article.url,
                    url_hash=article.url_hash,
                    published_date=article.published_date,
                    author=article.author,
                    keywords=article.keywords,
                    topic_id=article.topic_id,
                    check_duplicate=True,
                )
                
                if qdrant_point_id:
                    # Mettre à jour l'article avec le point_id
                    await update_qdrant_point_id(db_session, article, qdrant_point_id)
                    stats["indexed"] += 1
                    
                    if stats["indexed"] % 10 == 0:
                        logger.info(
                            "Progress",
                            indexed=stats["indexed"],
                            total=len(articles),
                            progress_pct=round((stats["indexed"] / len(articles)) * 100, 1),
                        )
                else:
                    # Doublon détecté
                    stats["duplicates"] += 1
                    logger.debug(
                        "Article is duplicate",
                        article_id=article.id,
                        domain=article.domain,
                    )
                
                # Commit périodique pour éviter les transactions trop longues
                if i % batch_size == 0:
                    await db_session.commit()
                    logger.debug("Batch committed", batch_size=batch_size)
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    "Failed to index article",
                    article_id=article.id,
                    domain=article.domain,
                    error=str(e),
                )
                continue
        
        # Commit final
        await db_session.commit()
    
    logger.info(
        "Indexing completed",
        **stats,
        domain=domain or "all",
    )
    
    return stats


async def main() -> None:
    """Point d'entrée principal."""
    domain = sys.argv[1] if len(sys.argv) > 1 else None
    
    if domain:
        print(f"🔍 Indexation des articles pour le domaine: {domain}")
    else:
        print("🔍 Indexation de tous les articles existants...")
    
    print("⏳ Démarrage de l'indexation...\n")
    
    stats = await index_existing_articles(domain=domain)
    
    print(f"\n✅ Indexation terminée:")
    print(f"  📊 Total d'articles trouvés: {stats['total']}")
    print(f"  ✅ Indexés avec succès: {stats['indexed']}")
    print(f"  🔄 Doublons détectés: {stats['duplicates']}")
    print(f"  ❌ Erreurs: {stats['errors']}")
    
    if stats['total'] > 0:
        success_rate = round((stats['indexed'] / stats['total']) * 100, 1)
        print(f"  📈 Taux de succès: {success_rate}%")


if __name__ == "__main__":
    asyncio.run(main())

