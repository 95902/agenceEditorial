"""Script de diagnostic pour comprendre pourquoi la route /topics retourne 0 résultats."""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    SiteProfile,
    ClientArticle,
    TrendPipelineExecution,
    TopicCluster,
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis


async def diagnose_topics_route(
    site_client: str = "innosys.fr",
    domain_topic: str = "Cloud Infrastructure Management",
) -> Dict[str, Any]:
    """
    Diagnostique pourquoi la route /topics retourne 0 résultats.
    
    Args:
        site_client: Client site identifier
        domain_topic: Activity domain label
        
    Returns:
        Dictionary with diagnostic information
    """
    async with AsyncSessionLocal() as db:
        # 1. Get site profile
        profile = await get_site_profile_by_domain(db, site_client)
        if not profile:
            return {
                "error": f"Site profile not found for: {site_client}",
            }
        
        print(f"✓ Site profile found: {profile.domain} (ID: {profile.id})")
        
        # 2. Check activity domains
        activity_domains = profile.activity_domains or {}
        primary_domains = activity_domains.get("primary_domains", [])
        secondary_domains = activity_domains.get("secondary_domains", [])
        all_domains = primary_domains + secondary_domains
        
        print(f"✓ Activity domains: {len(all_domains)} total")
        print(f"  - Primary: {primary_domains}")
        print(f"  - Secondary: {secondary_domains}")
        
        if domain_topic not in all_domains:
            return {
                "error": f"Domain '{domain_topic}' not found in activity domains",
                "available_domains": all_domains,
            }
        
        print(f"✓ Domain '{domain_topic}' found in activity domains")
        
        # 3. Get trend pipeline execution
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
            return {
                "error": f"No completed trend pipeline execution found for {profile.domain}",
            }
        
        print(f"✓ Trend pipeline execution found: {trend_execution.execution_id}")
        print(f"  - Total clusters: {trend_execution.total_clusters}")
        print(f"  - Total articles: {trend_execution.total_articles}")
        
        # 4. Get clusters
        clusters = await get_topic_clusters_by_analysis(
            db,
            trend_execution.id,
            scope=None,
            only_valid=True,
        )
        
        print(f"✓ Clusters found: {len(clusters)}")
        
        # 5. Get client articles
        articles_stmt = (
            select(ClientArticle)
            .where(
                ClientArticle.site_profile_id == profile.id,
                ClientArticle.is_valid == True,  # noqa: E712
            )
        )
        articles_result = await db.execute(articles_stmt)
        all_articles = list(articles_result.scalars().all())
        
        articles_with_topic_id = [art for art in all_articles if art.topic_id is not None]
        articles_with_qdrant_id = [art for art in all_articles if art.qdrant_point_id is not None]
        
        print(f"✓ Client articles: {len(all_articles)} total")
        print(f"  - With topic_id: {len(articles_with_topic_id)}")
        print(f"  - With qdrant_point_id: {len(articles_with_qdrant_id)}")
        
        # 6. Check clusters and their articles
        cluster_details = []
        for cluster in clusters:
            # Articles by topic_id
            articles_by_topic = [
                art for art in all_articles
                if art.topic_id == cluster.topic_id
            ]
            
            # Articles by document_ids
            articles_by_doc_ids = []
            if cluster.document_ids:
                doc_ids = cluster.document_ids.get("ids", []) or []
                if isinstance(doc_ids, list):
                    doc_ids_str = {str(doc_id).lower() for doc_id in doc_ids}
                    articles_by_doc_ids = [
                        art for art in all_articles
                        if art.qdrant_point_id and str(art.qdrant_point_id).lower() in doc_ids_str
                    ]
            
            # Check domain matching
            all_cluster_articles = articles_by_topic or articles_by_doc_ids
            matching_articles = []
            if all_cluster_articles:
                domain_keywords = set(domain_topic.lower().split())
                for art in all_cluster_articles:
                    title_lower = art.title.lower() if art.title else ""
                    if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
                        matching_articles.append(art)
                        continue
                    
                    if art.keywords:
                        keywords = art.keywords
                        if isinstance(keywords, dict):
                            primary_keywords = keywords.get("primary_keywords", [])
                            if isinstance(primary_keywords, list):
                                keywords_str = " ".join(str(k).lower() for k in primary_keywords)
                                if any(keyword in keywords_str for keyword in domain_keywords if len(keyword) > 3):
                                    matching_articles.append(art)
            
            cluster_details.append({
                "cluster_id": cluster.id,
                "topic_id": cluster.topic_id,
                "label": cluster.label,
                "size": cluster.size,
                "articles_by_topic_id": len(articles_by_topic),
                "articles_by_doc_ids": len(articles_by_doc_ids),
                "total_articles": len(all_cluster_articles),
                "matching_domain": len(matching_articles),
                "document_ids_count": len(cluster.document_ids.get("ids", [])) if cluster.document_ids else 0,
            })
        
        # 7. Summary
        relevant_clusters = [c for c in cluster_details if c["matching_domain"] > 0]
        
        return {
            "site_profile": {
                "domain": profile.domain,
                "id": profile.id,
            },
            "domain_topic": domain_topic,
            "trend_pipeline": {
                "execution_id": str(trend_execution.execution_id),
                "total_clusters": trend_execution.total_clusters,
                "total_articles": trend_execution.total_articles,
            },
            "articles": {
                "total": len(all_articles),
                "with_topic_id": len(articles_with_topic_id),
                "with_qdrant_point_id": len(articles_with_qdrant_id),
            },
            "clusters": {
                "total": len(clusters),
                "relevant": len(relevant_clusters),
                "details": cluster_details,
            },
            "diagnosis": {
                "has_trend_pipeline": True,
                "has_clusters": len(clusters) > 0,
                "has_articles": len(all_articles) > 0,
                "articles_have_topic_id": len(articles_with_topic_id) > 0,
                "articles_have_qdrant_id": len(articles_with_qdrant_id) > 0,
                "has_relevant_clusters": len(relevant_clusters) > 0,
            },
        }


async def main():
    """Main function."""
    result = await diagnose_topics_route(
        site_client="innosys.fr",
        domain_topic="Cloud Infrastructure Management",
    )
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLET")
    print("=" * 80)
    
    if "error" in result:
        print(f"❌ Erreur: {result['error']}")
        return
    
    print(f"\n📊 Résumé:")
    print(f"  - Clusters totaux: {result['clusters']['total']}")
    print(f"  - Clusters pertinents: {result['clusters']['relevant']}")
    print(f"  - Articles totaux: {result['articles']['total']}")
    print(f"  - Articles avec topic_id: {result['articles']['with_topic_id']}")
    print(f"  - Articles avec qdrant_point_id: {result['articles']['with_qdrant_point_id']}")
    
    print(f"\n🔍 Détails des clusters:")
    for cluster in result['clusters']['details']:
        print(f"  - Cluster {cluster['cluster_id']} (topic_id={cluster['topic_id']}):")
        print(f"    Label: {cluster['label']}")
        print(f"    Articles par topic_id: {cluster['articles_by_topic_id']}")
        print(f"    Articles par doc_ids: {cluster['articles_by_doc_ids']}")
        print(f"    Articles correspondant au domaine: {cluster['matching_domain']}")
        print(f"    document_ids dans cluster: {cluster['document_ids_count']}")
    
    print(f"\n💡 Diagnostic:")
    diagnosis = result['diagnosis']
    if not diagnosis['has_clusters']:
        print("  ❌ Aucun cluster trouvé")
    elif not diagnosis['articles_have_topic_id'] and not diagnosis['articles_have_qdrant_id']:
        print("  ❌ Articles sans topic_id ni qdrant_point_id")
    elif not diagnosis['articles_have_topic_id']:
        print("  ⚠️  Articles sans topic_id (utilise document_ids)")
    elif not diagnosis['has_relevant_clusters']:
        print("  ⚠️  Clusters trouvés mais aucun ne correspond au domaine")
    else:
        print("  ✅ Tout semble correct, mais la route retourne 0 topics")
    
    # Save to JSON
    import json
    with open("diagnostic_topics_route.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 Résultats sauvegardés dans: diagnostic_topics_route.json")


if __name__ == "__main__":
    asyncio.run(main())




