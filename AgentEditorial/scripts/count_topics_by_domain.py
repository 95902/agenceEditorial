"""Script pour compter les topics (articles) par domaine d'activité pour innosys."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    SiteProfile, 
    ClientArticle, 
    TrendPipelineExecution,
    TopicCluster
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.crud_client_articles import list_client_articles


def _count_articles_for_domain(
    articles: List[ClientArticle], domain_label: str
) -> int:
    """
    Count articles that match a domain label.
    
    Uses heuristics: check if domain keywords appear in article title or keywords.
    """
    if not articles or not domain_label:
        return 0
    
    # Extract keywords from domain label
    domain_keywords = set(domain_label.lower().split())
    
    count = 0
    for article in articles:
        # Check title
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            count += 1
            continue
        
        # Check keywords field
        if hasattr(article, "keywords") and article.keywords:
            keywords = article.keywords
            if isinstance(keywords, dict):
                primary_keywords = keywords.get("primary_keywords", [])
                if isinstance(primary_keywords, list):
                    keywords_str = " ".join(str(k).lower() for k in primary_keywords)
                    if any(keyword in keywords_str for keyword in domain_keywords if len(keyword) > 3):
                        count += 1
                        continue
    
    return count


async def count_topics_by_domain(domain: str = "innosys.fr") -> Dict[str, Any]:
    """
    Count topics (articles) per activity domain for a given site.
    
    Args:
        domain: Domain name (default: "innosys.fr")
        
    Returns:
        Dictionary with domain counts and details
    """
    async with AsyncSessionLocal() as db:
        # 1. Get site profile
        profile = await get_site_profile_by_domain(db, domain)
        if not profile:
            return {
                "error": f"Site profile not found for domain: {domain}",
                "domain": domain
            }
        
        # 2. Get activity domains
        activity_domains = profile.activity_domains or {}
        primary_domains = activity_domains.get("primary_domains", [])
        secondary_domains = activity_domains.get("secondary_domains", [])
        all_domains = primary_domains + secondary_domains
        
        if not all_domains:
            return {
                "error": f"No activity domains found for {domain}",
                "domain": domain,
                "profile_id": profile.id
            }
        
        # 3. Get all client articles
        client_articles = await list_client_articles(
            db, site_profile_id=profile.id, limit=10000
        )
        
        total_articles = len(client_articles)
        
        # 4. Count articles per domain
        domain_counts = {}
        for domain_label in all_domains:
            count = _count_articles_for_domain(client_articles, domain_label)
            domain_counts[domain_label] = {
                "topics_count": count,
                "percentage": round((count / total_articles * 100) if total_articles > 0 else 0, 2)
            }
        
        # 5. Check if domain_details exists in activity_domains
        domain_details = activity_domains.get("domain_details", {})
        stored_counts = {}
        if domain_details:
            for domain_slug, details in domain_details.items():
                if isinstance(details, dict):
                    stored_label = details.get("label", "")
                    stored_count = details.get("topics_count", 0)
                    if stored_label:
                        stored_counts[stored_label] = stored_count
        
        # 6. Get trend pipeline execution and topic clusters
        trend_execution = None
        topic_clusters_count = 0
        articles_with_topic_id = 0
        
        # Get latest trend pipeline execution for this domain
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
        
        if trend_execution:
            # Count topic clusters for this execution
            cluster_stmt = (
                select(func.count(TopicCluster.id))
                .where(
                    TopicCluster.analysis_id == trend_execution.id,
                    TopicCluster.is_valid == True  # noqa: E712
                )
            )
            cluster_result = await db.execute(cluster_stmt)
            topic_clusters_count = cluster_result.scalar_one() or 0
            
            # Count articles with topic_id assigned
            articles_with_topic_stmt = (
                select(func.count(ClientArticle.id))
                .where(
                    ClientArticle.site_profile_id == profile.id,
                    ClientArticle.topic_id.isnot(None),
                    ClientArticle.is_valid == True  # noqa: E712
                )
            )
            articles_with_topic_result = await db.execute(articles_with_topic_stmt)
            articles_with_topic_id = articles_with_topic_result.scalar_one() or 0
        
        # 7. Build comparison
        comparison = {}
        for domain_label in all_domains:
            calculated_count = domain_counts[domain_label]["topics_count"]
            stored_count = stored_counts.get(domain_label, None)
            
            comparison[domain_label] = {
                "calculated_count": calculated_count,
                "stored_count": stored_count,
                "match": calculated_count == stored_count if stored_count is not None else None,
                "difference": calculated_count - stored_count if stored_count is not None else None
            }
        
        # 8. Build result
        result = {
            "domain": domain,
            "profile_id": profile.id,
            "total_articles": total_articles,
            "primary_domains": primary_domains,
            "secondary_domains": secondary_domains,
            "topics_by_domain": domain_counts,
            "stored_counts": stored_counts,
            "comparison": comparison,
            "trend_pipeline": {
                "has_execution": trend_execution is not None,
                "execution_id": str(trend_execution.execution_id) if trend_execution else None,
                "total_clusters": topic_clusters_count,
                "articles_with_topic_id": articles_with_topic_id,
                "articles_without_topic_id": total_articles - articles_with_topic_id
            },
            "summary": {
                "total_domains": len(all_domains),
                "domains_with_articles": sum(1 for d in domain_counts.values() if d["topics_count"] > 0),
                "domains_without_articles": sum(1 for d in domain_counts.values() if d["topics_count"] == 0),
                "domains_with_stored_data": len(stored_counts),
                "domains_matching": sum(1 for c in comparison.values() if c["match"] is True),
                "domains_differing": sum(1 for c in comparison.values() if c["match"] is False),
                "domains_not_stored": sum(1 for c in comparison.values() if c["stored_count"] is None),
                "total_topic_clusters": topic_clusters_count,
                "articles_assigned_to_topics": articles_with_topic_id
            }
        }
        
        return result


async def main():
    """Main function."""
    print("🔍 Recherche des topics par domaine pour innosys.fr...\n")
    
    result = await count_topics_by_domain("innosys.fr")
    
    if "error" in result:
        print(f"❌ Erreur: {result['error']}")
        return
    
    print(f"📊 Résultats pour {result['domain']}")
    print(f"   Profile ID: {result['profile_id']}")
    print(f"   Total articles: {result['total_articles']}\n")
    
    print("📈 Topics par domaine d'activité (calculé):\n")
    
    # Sort by count descending
    sorted_domains = sorted(
        result["topics_by_domain"].items(),
        key=lambda x: x[1]["topics_count"],
        reverse=True
    )
    
    for domain_label, data in sorted_domains:
        count = data["topics_count"]
        percentage = data["percentage"]
        bar = "█" * min(int(percentage / 2), 50)  # Bar chart
        print(f"  {domain_label:40} {count:4} topics ({percentage:5.1f}%) {bar}")
    
    print(f"\n📋 Comparaison avec les données stockées:\n")
    
    for domain_label, comp in result["comparison"].items():
        calc = comp["calculated_count"]
        stored = comp["stored_count"]
        
        if stored is not None:
            match_symbol = "✅" if comp["match"] else "❌"
            diff = comp["difference"]
            diff_str = f"({diff:+d})" if diff != 0 else ""
            print(f"  {match_symbol} {domain_label:40} Calculé: {calc:4} | Stocké: {stored:4} {diff_str}")
        else:
            print(f"  ⚠️  {domain_label:40} Calculé: {calc:4} | Stocké: (non stocké)")
    
    print(f"\n📊 Résumé:")
    print(f"   - Total domaines: {result['summary']['total_domains']}")
    print(f"   - Domaines avec articles: {result['summary']['domains_with_articles']}")
    print(f"   - Domaines sans articles: {result['summary']['domains_without_articles']}")
    print(f"   - Domaines avec données stockées: {result['summary']['domains_with_stored_data']}")
    print(f"   - Domaines correspondants: {result['summary']['domains_matching']}")
    print(f"   - Domaines différents: {result['summary']['domains_differing']}")
    print(f"   - Domaines non stockés: {result['summary']['domains_not_stored']}")
    
    print(f"\n🔬 Trend Pipeline:")
    if result['trend_pipeline']['has_execution']:
        print(f"   ✅ Exécution trouvée: {result['trend_pipeline']['execution_id']}")
        print(f"   - Total topic clusters: {result['trend_pipeline']['total_clusters']}")
        print(f"   - Articles avec topic_id: {result['trend_pipeline']['articles_with_topic_id']}")
        print(f"   - Articles sans topic_id: {result['trend_pipeline']['articles_without_topic_id']}")
        
        # Comparaison
        total_calculated = sum(d["topics_count"] for d in result["topics_by_domain"].values())
        print(f"\n📈 Comparaison:")
        print(f"   - Total articles calculés par domaine: {total_calculated}")
        print(f"   - Total topic clusters (BERTopic): {result['trend_pipeline']['total_clusters']}")
        print(f"   - Articles assignés à un topic: {result['trend_pipeline']['articles_with_topic_id']}")
        
        if total_calculated > 0:
            ratio = (result['trend_pipeline']['articles_with_topic_id'] / total_calculated) * 100
            print(f"   - Ratio articles assignés/articles calculés: {ratio:.1f}%")
    else:
        print(f"   ⚠️  Aucune exécution de trend pipeline trouvée")
    
    # Save to JSON file
    output_file = "innosys_topics_by_domain.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Résultats sauvegardés dans: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())

