#!/usr/bin/env python3
"""
Analyse des concurrents : nombre trouvés vs nombre scrapés

Ce script :
1. Récupère la liste complète des concurrents trouvés
2. Vérifie combien ont été scrapés (ont des articles)
3. Affiche les statistiques détaillées
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution, CompetitorArticle
from python_scripts.database.crud_articles import count_competitor_articles


async def analyze_competitors_scraping(domain: str = "innosys.fr"):
    """Analyse les concurrents trouvés et scrapés."""
    async with AsyncSessionLocal() as db:
        # 1. Récupérer la dernière exécution de recherche de concurrents
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(1)
        )
        
        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()
        
        if not execution or not execution.output_data:
            print(f"❌ Aucune recherche de concurrents trouvée pour {domain}")
            return
        
        competitors_data = execution.output_data.get("competitors", [])
        all_candidates = execution.output_data.get("all_candidates", [])
        excluded_candidates = execution.output_data.get("excluded_candidates", [])
        
        print("="*80)
        print(f"ANALYSE DES CONCURRENTS - {domain}")
        print("="*80)
        print(f"\n📊 STATISTIQUES GÉNÉRALES")
        print("-"*80)
        
        # Nombre total de candidats trouvés
        total_found = execution.output_data.get("total_found", len(all_candidates) if all_candidates else len(competitors_data))
        print(f"Total de candidats trouvés: {total_found}")
        
        # Nombre de concurrents inclus
        total_included = len(competitors_data)
        print(f"Concurrents inclus (final): {total_included}")
        
        # Nombre de concurrents exclus
        total_excluded = len(excluded_candidates) if excluded_candidates else 0
        print(f"Concurrents exclus: {total_excluded}")
        
        # Concurrents validés
        validated_competitors = [
            c for c in competitors_data
            if c.get("validated", False) or c.get("manual", False)
        ]
        print(f"Concurrents validés: {len(validated_competitors)}")
        
        # Concurrents non exclus
        non_excluded = [
            c for c in competitors_data
            if not c.get("excluded", False)
        ]
        print(f"Concurrents non exclus: {len(non_excluded)}")
        
        # 2. Vérifier combien ont été scrapés
        print(f"\n📰 ANALYSE DU SCRAPING")
        print("-"*80)
        
        # Utiliser les concurrents validés ou tous les non exclus
        competitors_to_check = validated_competitors if validated_competitors else non_excluded
        
        scraped_count = 0
        not_scraped = []
        scraping_stats = []
        
        for competitor in competitors_to_check:
            comp_domain = competitor.get("domain")
            if not comp_domain:
                continue
            
            # Compter les articles pour ce concurrent
            article_count = await count_competitor_articles(db, domain=comp_domain)
            
            if article_count > 0:
                scraped_count += 1
                scraping_stats.append({
                    "domain": comp_domain,
                    "articles": article_count,
                    "validated": competitor.get("validated", False),
                    "similarity": competitor.get("relevance_score", 0) * 100 if competitor.get("relevance_score") else 0
                })
            else:
                not_scraped.append({
                    "domain": comp_domain,
                    "validated": competitor.get("validated", False),
                    "similarity": competitor.get("relevance_score", 0) * 100 if competitor.get("relevance_score") else 0
                })
        
        print(f"Concurrents à vérifier: {len(competitors_to_check)}")
        print(f"✅ Concurrents scrapés (avec articles): {scraped_count}")
        print(f"❌ Concurrents non scrapés (sans articles): {len(not_scraped)}")
        
        # Statistiques sur les articles
        total_articles = sum(s["articles"] for s in scraping_stats)
        avg_articles = total_articles / scraped_count if scraped_count > 0 else 0
        
        print(f"\n📈 STATISTIQUES DES ARTICLES")
        print("-"*80)
        print(f"Total d'articles scrapés: {total_articles}")
        print(f"Moyenne d'articles par concurrent scrapé: {avg_articles:.1f}")
        
        if scraping_stats:
            max_articles = max(s["articles"] for s in scraping_stats)
            min_articles = min(s["articles"] for s in scraping_stats)
            print(f"Min articles: {min_articles}, Max articles: {max_articles}")
        
        # Détail des concurrents scrapés
        if scraping_stats:
            print(f"\n✅ CONCURRENTS SCRAPÉS ({scraped_count})")
            print("-"*80)
            # Trier par nombre d'articles décroissant
            scraping_stats.sort(key=lambda x: x["articles"], reverse=True)
            for i, stat in enumerate(scraping_stats, 1):
                validated_marker = "✓" if stat["validated"] else " "
                print(f"{i}. {stat['domain']}")
                print(f"   Articles: {stat['articles']} | Similarité: {stat['similarity']:.0f}% | Validé: {validated_marker}")
        
        # Détail des concurrents non scrapés
        if not_scraped:
            print(f"\n❌ CONCURRENTS NON SCRAPÉS ({len(not_scraped)})")
            print("-"*80)
            for i, comp in enumerate(not_scraped, 1):
                validated_marker = "✓" if comp["validated"] else " "
                print(f"{i}. {comp['domain']}")
                print(f"   Similarité: {comp['similarity']:.0f}% | Validé: {validated_marker}")
        
        # Résumé final
        print(f"\n{'='*80}")
        print("RÉSUMÉ")
        print(f"{'='*80}")
        print(f"📊 Candidats trouvés: {total_found}")
        print(f"✅ Concurrents inclus: {total_included}")
        print(f"   └─ Validés: {len(validated_competitors)}")
        print(f"   └─ Non exclus: {len(non_excluded)}")
        print(f"📰 Concurrents scrapés: {scraped_count}/{len(competitors_to_check)} ({scraped_count/len(competitors_to_check)*100:.1f}%)" if competitors_to_check else "📰 Concurrents scrapés: 0/0")
        print(f"📄 Total articles scrapés: {total_articles}")
        
        if competitors_to_check and scraped_count < len(competitors_to_check):
            print(f"\n⚠️ {len(not_scraped)} concurrent(s) n'ont pas encore été scrapés.")
            print("   Lancer le scraping pour ces concurrents pour enrichir les données.")
        
        print("="*80)


async def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyse des concurrents trouvés vs scrapés"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)"
    )
    
    args = parser.parse_args()
    
    await analyze_competitors_scraping(args.domain)


if __name__ == "__main__":
    asyncio.run(main())


