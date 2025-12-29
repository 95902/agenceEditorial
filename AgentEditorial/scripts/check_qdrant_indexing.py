"""Script pour vérifier l'indexation Qdrant et l'assignation des topic_id."""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

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


async def check_qdrant_indexing(domain: str = "innosys.fr") -> Dict[str, Any]:
    """
    Check Qdrant indexing and topic_id assignment for a domain.
    
    Args:
        domain: Domain name (default: "innosys.fr")
        
    Returns:
        Dictionary with indexing and assignment details
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
        
        total_articles = len(client_articles)
        
        # 3. Check Qdrant collection
        collection_name = get_client_collection_name(domain)
        collection_exists = qdrant_client.collection_exists(collection_name)
        
        # 4. Count articles with qdrant_point_id
        articles_with_qdrant_id = sum(
            1 for article in client_articles 
            if article.qdrant_point_id is not None
        )
        
        # 5. Count articles with topic_id
        articles_with_topic_id = sum(
            1 for article in client_articles 
            if article.topic_id is not None
        )
        
        # 6. Get Qdrant collection info if exists
        qdrant_info = {}
        if collection_exists:
            try:
                collection_info = qdrant_client.client.get_collection(collection_name)
                qdrant_info = {
                    "points_count": collection_info.points_count,
                    "vectors_count": collection_info.vectors_count,
                    "config": {
                        "vector_size": collection_info.config.params.vectors.size,
                        "distance": str(collection_info.config.params.vectors.distance)
                    }
                }
            except Exception as e:
                qdrant_info = {"error": str(e)}
        
        # 7. Get trend pipeline execution
        from sqlalchemy import desc
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
        
        # 8. Get topic clusters info
        topic_clusters_info = {}
        if trend_execution:
            # Count clusters
            cluster_stmt = (
                select(func.count(TopicCluster.id))
                .where(
                    TopicCluster.analysis_id == trend_execution.id,
                    TopicCluster.is_valid == True  # noqa: E712
                )
            )
            cluster_result = await db.execute(cluster_stmt)
            total_clusters = cluster_result.scalar_one() or 0
            
            # Get clusters with size
            clusters_stmt = (
                select(TopicCluster)
                .where(
                    TopicCluster.analysis_id == trend_execution.id,
                    TopicCluster.is_valid == True  # noqa: E712
                )
            )
            clusters_result = await db.execute(clusters_stmt)
            clusters = clusters_result.scalars().all()
            
            # Calculate total documents in clusters
            total_documents_in_clusters = sum(
                cluster.size for cluster in clusters
            )
            
            topic_clusters_info = {
                "total_clusters": total_clusters,
                "total_documents_in_clusters": total_documents_in_clusters,
                "execution_id": str(trend_execution.execution_id),
                "clusters": [
                    {
                        "topic_id": cluster.topic_id,
                        "label": cluster.label,
                        "size": cluster.size,
                        "scope": cluster.scope
                    }
                    for cluster in clusters[:10]  # Limit to 10 for display
                ]
            }
        
        # 9. Build result
        result = {
            "domain": domain,
            "profile_id": profile.id,
            "total_articles": total_articles,
            "qdrant": {
                "collection_name": collection_name,
                "collection_exists": collection_exists,
                "articles_with_qdrant_point_id": articles_with_qdrant_id,
                "articles_without_qdrant_point_id": total_articles - articles_with_qdrant_id,
                "collection_info": qdrant_info
            },
            "topic_assignment": {
                "articles_with_topic_id": articles_with_topic_id,
                "articles_without_topic_id": total_articles - articles_with_topic_id,
                "percentage_assigned": round((articles_with_topic_id / total_articles * 100) if total_articles > 0 else 0, 2)
            },
            "trend_pipeline": topic_clusters_info,
            "summary": {
                "total_articles": total_articles,
                "indexed_in_qdrant": articles_with_qdrant_id,
                "not_indexed_in_qdrant": total_articles - articles_with_qdrant_id,
                "assigned_to_topic": articles_with_topic_id,
                "not_assigned_to_topic": total_articles - articles_with_topic_id,
                "qdrant_points": qdrant_info.get("points_count", 0) if isinstance(qdrant_info, dict) else 0,
                "topic_clusters": topic_clusters_info.get("total_clusters", 0) if topic_clusters_info else 0
            }
        }
        
        return result


async def main():
    """Main function."""
    print("🔍 Vérification de l'indexation Qdrant et de l'assignation des topic_id...\n")
    
    result = await check_qdrant_indexing("innosys.fr")
    
    if "error" in result:
        print(f"❌ Erreur: {result['error']}")
        return
    
    print(f"📊 Résultats pour {result['domain']}")
    print(f"   Profile ID: {result['profile_id']}")
    print(f"   Total articles: {result['total_articles']}\n")
    
    # Qdrant info
    print("🗄️  Indexation Qdrant:")
    qdrant = result['qdrant']
    print(f"   Collection: {qdrant['collection_name']}")
    print(f"   Collection existe: {'✅ Oui' if qdrant['collection_exists'] else '❌ Non'}")
    print(f"   Articles avec qdrant_point_id: {qdrant['articles_with_qdrant_point_id']}")
    print(f"   Articles sans qdrant_point_id: {qdrant['articles_without_qdrant_point_id']}")
    
    if qdrant['collection_exists'] and isinstance(qdrant['collection_info'], dict):
        info = qdrant['collection_info']
        if 'points_count' in info:
            print(f"   Points dans Qdrant: {info['points_count']}")
            print(f"   Vecteurs dans Qdrant: {info['vectors_count']}")
            if 'config' in info:
                print(f"   Taille des vecteurs: {info['config']['vector_size']}")
                print(f"   Distance: {info['config']['distance']}")
    
    # Topic assignment
    print(f"\n🏷️  Assignation des topic_id:")
    topic_assignment = result['topic_assignment']
    print(f"   Articles avec topic_id: {topic_assignment['articles_with_topic_id']}")
    print(f"   Articles sans topic_id: {topic_assignment['articles_without_topic_id']}")
    print(f"   Pourcentage assigné: {topic_assignment['percentage_assigned']}%")
    
    # Trend pipeline
    print(f"\n📈 Trend Pipeline:")
    if result['trend_pipeline']:
        tp = result['trend_pipeline']
        print(f"   ✅ Exécution trouvée: {tp['execution_id']}")
        print(f"   Total clusters: {tp['total_clusters']}")
        print(f"   Total documents dans clusters: {tp['total_documents_in_clusters']}")
        
        if tp['clusters']:
            print(f"\n   Top 10 clusters:")
            for cluster in tp['clusters']:
                print(f"      - Topic {cluster['topic_id']}: {cluster['label'][:50]} ({cluster['size']} docs, scope: {cluster['scope']})")
    else:
        print(f"   ⚠️  Aucune exécution de trend pipeline trouvée")
    
    # Summary
    print(f"\n📋 Résumé:")
    summary = result['summary']
    print(f"   - Total articles: {summary['total_articles']}")
    print(f"   - Indexés dans Qdrant: {summary['indexed_in_qdrant']} ({summary['qdrant_points']} points)")
    print(f"   - Non indexés: {summary['not_indexed_in_qdrant']}")
    print(f"   - Assignés à un topic: {summary['assigned_to_topic']}")
    print(f"   - Non assignés: {summary['not_assigned_to_topic']}")
    print(f"   - Topic clusters disponibles: {summary['topic_clusters']}")
    
    # Diagnostic
    print(f"\n🔬 Diagnostic:")
    issues = []
    if summary['not_indexed_in_qdrant'] > 0:
        issues.append(f"⚠️  {summary['not_indexed_in_qdrant']} articles ne sont pas indexés dans Qdrant")
    if summary['not_assigned_to_topic'] > 0 and summary['topic_clusters'] > 0:
        issues.append(f"⚠️  {summary['not_assigned_to_topic']} articles ne sont pas assignés à un topic (alors que {summary['topic_clusters']} clusters existent)")
    if summary['qdrant_points'] != summary['indexed_in_qdrant']:
        issues.append(f"⚠️  Incohérence: {summary['indexed_in_qdrant']} articles avec qdrant_point_id mais {summary['qdrant_points']} points dans Qdrant")
    
    if issues:
        for issue in issues:
            print(f"   {issue}")
    else:
        print(f"   ✅ Tout semble correct !")


if __name__ == "__main__":
    asyncio.run(main())





