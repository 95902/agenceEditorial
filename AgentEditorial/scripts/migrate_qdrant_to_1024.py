#!/usr/bin/env python3
"""
Script de migration de la collection Qdrant de 384 à 1024 dimensions.

Ce script :
1. Sauvegarde les métadonnées des articles existants
2. Supprime l'ancienne collection (384 dimensions)
3. Crée une nouvelle collection (1024 dimensions avec mxbai-embed-large-v1)
4. Réindexe tous les articles avec le nouveau modèle d'embedding

ATTENTION: Ce script supprime l'ancienne collection. Assurez-vous d'avoir une sauvegarde.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import CompetitorArticle
from python_scripts.utils.logging import setup_logging, get_logger
from python_scripts.vectorstore.qdrant_client import qdrant_client
from python_scripts.vectorstore.embeddings_utils import generate_embedding

setup_logging()
logger = get_logger(__name__)

COLLECTION_NAME = "competitor_articles"
OLD_DIMENSION = 384
NEW_DIMENSION = 1024


async def migrate_collection() -> dict[str, int]:
    """
    Migre la collection Qdrant de 384 à 1024 dimensions.
    
    Returns:
        Statistiques de migration (articles_migrated, errors)
    """
    stats = {"articles_migrated": 0, "errors": 0, "total_articles": 0}
    
    # Vérifier que la collection existe
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        logger.warning("Collection does not exist", collection=COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' does not exist. Nothing to migrate.")
        return stats
    
    # Récupérer tous les articles depuis PostgreSQL
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(CompetitorArticle).where(
                CompetitorArticle.is_valid == True,  # noqa: E712
                CompetitorArticle.qdrant_point_id.isnot(None),
            )
        )
        articles = list(result.scalars().all())
        stats["total_articles"] = len(articles)
    
    if stats["total_articles"] == 0:
        logger.info("No articles to migrate")
        print("No articles found in database. Nothing to migrate.")
        return stats
    
    print(f"\n{'='*60}")
    print(f"Migration de la collection Qdrant")
    print(f"{'='*60}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Ancienne dimension: {OLD_DIMENSION}")
    print(f"Nouvelle dimension: {NEW_DIMENSION}")
    print(f"Articles à migrer: {stats['total_articles']}")
    print(f"{'='*60}\n")
    
    # Confirmation
    response = input("Voulez-vous continuer? (oui/non): ")
    if response.lower() not in ("oui", "o", "yes", "y"):
        print("Migration annulée.")
        return stats
    
    try:
        # Étape 1: Supprimer l'ancienne collection
        logger.info("Deleting old collection", collection=COLLECTION_NAME)
        print(f"Suppression de l'ancienne collection '{COLLECTION_NAME}'...")
        try:
            qdrant_client.client.delete_collection(COLLECTION_NAME)
            logger.info("Old collection deleted")
            print("✓ Ancienne collection supprimée")
        except Exception as e:
            logger.warning("Collection might not exist or already deleted", error=str(e))
            print(f"⚠ Collection peut-être déjà supprimée: {e}")
        
        # Étape 2: Créer la nouvelle collection avec 1024 dimensions
        logger.info("Creating new collection", collection=COLLECTION_NAME, dimension=NEW_DIMENSION)
        print(f"\nCréation de la nouvelle collection '{COLLECTION_NAME}' ({NEW_DIMENSION} dimensions)...")
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vector_size=NEW_DIMENSION,
        )
        logger.info("New collection created")
        print("✓ Nouvelle collection créée")
        
        # Étape 3: Réindexer tous les articles
        print(f"\nRéindexation des articles avec le nouveau modèle (mxbai-embed-large-v1)...")
        print(f"Ce processus peut prendre du temps...\n")
        
        async with AsyncSessionLocal() as db_session:
            for i, article in enumerate(articles, 1):
                try:
                    # Générer le nouvel embedding avec mxbai-embed-large-v1
                    text_for_embedding = f"{article.title}\n{article.content_text[:2000]}"
                    embedding = generate_embedding(text_for_embedding)
                    
                    # Vérifier la dimension
                    if len(embedding) != NEW_DIMENSION:
                        logger.error(
                            "Embedding dimension mismatch",
                            article_id=article.id,
                            expected=NEW_DIMENSION,
                            got=len(embedding),
                        )
                        stats["errors"] += 1
                        continue
                    
                    # Indexer dans Qdrant
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
                        check_duplicate=False,  # Pas besoin de vérifier les doublons lors de la migration
                    )
                    
                    if qdrant_point_id:
                        # Mettre à jour l'article avec le nouveau point_id
                        from python_scripts.database.crud_articles import update_qdrant_point_id
                        await update_qdrant_point_id(db_session, article, qdrant_point_id)
                        stats["articles_migrated"] += 1
                        
                        if i % 10 == 0:
                            progress = (i / stats["total_articles"]) * 100
                            print(f"  Progression: {i}/{stats['total_articles']} ({progress:.1f}%)")
                    else:
                        stats["errors"] += 1
                        logger.warning("Failed to index article", article_id=article.id)
                    
                    # Commit périodique
                    if i % 50 == 0:
                        await db_session.commit()
                
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        "Error migrating article",
                        article_id=article.id,
                        error=str(e),
                    )
                    continue
            
            # Commit final
            await db_session.commit()
        
        print(f"\n{'='*60}")
        print(f"Migration terminée!")
        print(f"{'='*60}")
        print(f"Articles migrés: {stats['articles_migrated']}/{stats['total_articles']}")
        print(f"Erreurs: {stats['errors']}")
        print(f"{'='*60}\n")
        
        logger.info(
            "Migration completed",
            migrated=stats["articles_migrated"],
            total=stats["total_articles"],
            errors=stats["errors"],
        )
        
        return stats
        
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        print(f"\n❌ Erreur lors de la migration: {e}")
        raise


if __name__ == "__main__":
    try:
        stats = asyncio.run(migrate_collection())
        sys.exit(0 if stats["errors"] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\nMigration interrompue par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)

