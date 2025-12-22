"""Script pour vérifier et corriger l'indexation Qdrant et l'assignation des topic_id."""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, update

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    SiteProfile, 
    ClientArticle, 
    TrendPipelineExecution,
    TopicCluster
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.crud_client_articles import list_client_articles
from python_scripts.vectorstore.qdrant_client import (
    qdrant_client,
    get_client_collection_name
)


async def verify_points_in_qdrant(
    collection_name: str,
    point_ids: List[UUID]
) -> Dict[str, Any]:
    """
    Verify if points exist in Qdrant collection.
    
    Args:
        collection_name: Qdrant collection name
        point_ids: List of point IDs to check
        
    Returns:
        Dictionary with verification results
    """
    if not qdrant_client.collection_exists(collection_name):
        return {
            "collection_exists": False,
            "points_found": 0,
            "points_missing": len(point_ids),
            "details": []
        }
    
    try:
        # Try to retrieve points by IDs
        from qdrant_client.models import PointIdsList
        
        result = qdrant_client.client.retrieve(
            collection_name=collection_name,
            ids=point_ids
        )
        
        points_found = len([p for p in result if p is not None])
        points_missing = len(point_ids) - points_found
        
        found_ids = [str(p.id) for p in result if p is not None]
        missing_ids = [
            str(pid) for pid in point_ids 
            if str(pid) not in found_ids
        ]
        
        return {
            "collection_exists": True,
            "points_found": points_found,
            "points_missing": points_missing,
            "found_ids": found_ids[:10],  # Limit for display
            "missing_ids": missing_ids[:10],  # Limit for display
            "total_checked": len(point_ids)
        }
    except Exception as e:
        return {
            "collection_exists": True,
            "error": str(e),
            "points_found": 0,
            "points_missing": len(point_ids)
        }


async def reindex_articles(
    db: AsyncSession,
    articles: List[ClientArticle],
    collection_name: str,
    domain: str
) -> Dict[str, Any]:
    """
    Reindex articles in Qdrant.
    
    Args:
        db: Database session
        articles: List of articles to reindex
        collection_name: Qdrant collection name
        domain: Domain name
        
    Returns:
        Dictionary with reindexing results
    """
    from python_scripts.vectorstore.qdrant_client import qdrant_client
    
    reindexed = 0
    errors = []
    
    for article in articles:
        try:
            # Index article
            qdrant_point_id = qdrant_client.index_article(
                article_id=article.id,
                domain=domain,
                title=article.title,
                content_text=article.content_text,
                url=article.url,
                url_hash=article.url_hash,
                published_date=article.published_date,
                author=article.author,
                keywords=article.keywords,
                topic_id=article.topic_id,
                check_duplicate=False,  # Skip duplicate check for reindexing
                collection_name=collection_name
            )
            
            if qdrant_point_id:
                # Update article with new qdrant_point_id
                article.qdrant_point_id = qdrant_point_id
                reindexed += 1
        except Exception as e:
            errors.append({
                "article_id": article.id,
                "error": str(e)
            })
    
    await db.commit()
    
    return {
        "reindexed": reindexed,
        "errors": errors,
        "total": len(articles)
    }


async def assign_topics_to_articles(
    db: AsyncSession,
    articles: List[ClientArticle],
    trend_execution: TrendPipelineExecution,
    collection_name: str,
    domain: str
) -> Dict[str, Any]:
    """
    Assign topic_id to articles based on Qdrant similarity search with competitor articles.
    
    Args:
        db: Database session
        articles: List of articles to assign
        trend_execution: Trend pipeline execution
        collection_name: Client articles collection name
        domain: Client domain name
        
    Returns:
        Dictionary with assignment results
    """
    # Get topic clusters
    stmt = (
        select(TopicCluster)
        .where(
            TopicCluster.analysis_id == trend_execution.id,
            TopicCluster.is_valid == True  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    clusters = result.scalars().all()
    
    if not clusters:
        return {
            "assigned": 0,
            "error": "No topic clusters found"
        }
    
    # Get competitor collection name (where articles with topic_id are stored)
    from python_scripts.vectorstore.qdrant_client import get_competitor_collection_name
    competitor_collection = get_competitor_collection_name(domain)
    
    # Check if competitor collection exists
    if not qdrant_client.collection_exists(competitor_collection):
        return {
            "assigned": 0,
            "error": f"Competitor collection {competitor_collection} does not exist"
        }
    
    assigned = 0
    errors = []
    
    from python_scripts.vectorstore.embeddings_utils import generate_embedding
    
    for article in articles:
        if not article.qdrant_point_id:
            continue  # Skip articles without Qdrant point
        
        try:
            # Generate embedding for article
            text_for_embedding = f"{article.title}\n{article.content_text[:2000]}"
            query_vector = generate_embedding(text_for_embedding)
            
            # Search for similar points in competitor collection (which have topic_id)
            search_results = qdrant_client.search(
                collection_name=competitor_collection,
                query_vector=query_vector,
                limit=10,
                score_threshold=0.6  # Lower threshold to find more matches
            )
            
            if not search_results:
                continue
            
            # Find the best matching topic_id from search results
            best_topic_id = None
            best_score = 0.0
            
            for result in search_results:
                payload = result.payload if hasattr(result, 'payload') else {}
                result_topic_id = payload.get('topic_id')
                
                if result_topic_id is not None and result.score > best_score:
                    # Verify this topic_id exists in clusters
                    for cluster in clusters:
                        if cluster.topic_id == result_topic_id:
                            best_score = result.score
                            best_topic_id = result_topic_id
                            break
            
            if best_topic_id and best_score >= 0.6:
                # Assign topic_id to article
                article.topic_id = best_topic_id
                assigned += 1
        except Exception as e:
            errors.append({
                "article_id": article.id,
                "error": str(e)
            })
    
    await db.commit()
    
    return {
        "assigned": assigned,
        "errors": errors,
        "total": len(articles)
    }


async def verify_and_fix(domain: str = "innosys.fr", fix: bool = False) -> Dict[str, Any]:
    """
    Verify Qdrant indexing and topic assignment, optionally fix issues.
    
    Args:
        domain: Domain name
        fix: Whether to fix issues (reindex and assign)
        
    Returns:
        Dictionary with verification and fix results
    """
    async with AsyncSessionLocal() as db:
        # 1. Get site profile
        profile = await get_site_profile_by_domain(db, domain)
        if not profile:
            return {
                "error": f"Site profile not found for domain: {domain}",
                "domain": domain
            }
        
        # 2. Get all client articles
        client_articles = await list_client_articles(
            db, site_profile_id=profile.id, limit=10000
        )
        
        # 3. Get Qdrant collection name
        collection_name = get_client_collection_name(domain)
        
        # 4. Verify points in Qdrant
        point_ids = [
            article.qdrant_point_id 
            for article in client_articles 
            if article.qdrant_point_id is not None
        ]
        
        verification = await verify_points_in_qdrant(collection_name, point_ids)
        
        # 5. Get trend pipeline execution
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == domain,
                TrendPipelineExecution.stage_1_clustering_status == "completed"
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_execution = result.scalar_one_or_none()
        
        # 6. Fix if requested
        fix_results = {}
        if fix:
            # Reindex missing articles
            articles_to_reindex = [
                article for article in client_articles
                if article.qdrant_point_id is None or 
                (article.qdrant_point_id and str(article.qdrant_point_id) not in verification.get("found_ids", []))
            ]
            
            if articles_to_reindex:
                reindex_result = await reindex_articles(
                    db, articles_to_reindex, collection_name, domain
                )
                fix_results["reindexing"] = reindex_result
            
            # Assign topics
            if trend_execution:
                articles_to_assign = [
                    article for article in client_articles
                    if article.topic_id is None and article.qdrant_point_id is not None
                ]
                
                if articles_to_assign:
                    assign_result = await assign_topics_to_articles(
                        db, articles_to_assign, trend_execution, collection_name, domain
                    )
                    fix_results["topic_assignment"] = assign_result
        
        # 7. Build result
        result = {
            "domain": domain,
            "profile_id": profile.id,
            "total_articles": len(client_articles),
            "verification": verification,
            "trend_pipeline": {
                "has_execution": trend_execution is not None,
                "execution_id": str(trend_execution.execution_id) if trend_execution else None
            },
            "fix_results": fix_results if fix else None
        }
        
        return result


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vérifier et corriger l'indexation Qdrant")
    parser.add_argument("--domain", default="innosys.fr", help="Domain name")
    parser.add_argument("--fix", action="store_true", help="Corriger les problèmes détectés")
    
    args = parser.parse_args()
    
    print("🔍 Vérification de l'indexation Qdrant et de l'assignation des topic_id...\n")
    
    result = await verify_and_fix(args.domain, fix=args.fix)
    
    if "error" in result:
        print(f"❌ Erreur: {result['error']}")
        return
    
    print(f"📊 Résultats pour {result['domain']}")
    print(f"   Profile ID: {result['profile_id']}")
    print(f"   Total articles: {result['total_articles']}\n")
    
    # Verification results
    verification = result['verification']
    print("🔍 Vérification Qdrant:")
    if not verification.get("collection_exists"):
        print(f"   ❌ Collection n'existe pas")
    else:
        print(f"   ✅ Collection existe")
        if "error" in verification:
            print(f"   ❌ Erreur lors de la vérification: {verification['error']}")
        else:
            print(f"   Points trouvés: {verification['points_found']}/{verification['total_checked']}")
            print(f"   Points manquants: {verification['points_missing']}")
            
            if verification['points_missing'] > 0:
                print(f"   ⚠️  {verification['points_missing']} points manquants dans Qdrant")
    
    # Fix results
    if result.get("fix_results"):
        print(f"\n🔧 Résultats de la correction:")
        
        if "reindexing" in result["fix_results"]:
            reindex = result["fix_results"]["reindexing"]
            print(f"   Réindexation: {reindex['reindexed']}/{reindex['total']} articles")
            if reindex.get("errors"):
                print(f"   ⚠️  {len(reindex['errors'])} erreurs lors de la réindexation")
        
        if "topic_assignment" in result["fix_results"]:
            assign = result["fix_results"]["topic_assignment"]
            if "error" in assign:
                print(f"   ❌ Erreur lors de l'assignation: {assign['error']}")
            else:
                print(f"   Assignation topics: {assign['assigned']}/{assign['total']} articles")
                if assign.get("errors"):
                    print(f"   ⚠️  {len(assign['errors'])} erreurs lors de l'assignation")
    
    # Recommendations
    print(f"\n💡 Recommandations:")
    if verification.get("points_missing", 0) > 0:
        print(f"   - Relancer l'indexation avec: python scripts/verify_and_fix_qdrant.py --domain {args.domain} --fix")
    else:
        print(f"   - Les points sont présents dans Qdrant")
    
    if result['trend_pipeline']['has_execution']:
        print(f"   - Trend pipeline disponible: {result['trend_pipeline']['execution_id']}")
    else:
        print(f"   - ⚠️  Aucun trend pipeline trouvé")


if __name__ == "__main__":
    asyncio.run(main())

