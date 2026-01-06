#!/usr/bin/env python3
"""Analyse la dernière recherche avec max_competitors=35"""

import asyncio
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.database.crud_articles import count_competitor_articles


async def analyze_latest_35(domain: str = "innosys.fr"):
    """Analyse la dernière recherche avec max_competitors=35."""
    async with AsyncSessionLocal() as db:
        # Chercher toutes les recherches complétées
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
        )
        
        result = await db.execute(stmt)
        executions = result.scalars().all()
        
        if not executions:
            print("❌ Aucune recherche trouvée")
            return
        
        print("="*80)
        print(f"TOUTES LES RECHERCHES POUR {domain}")
        print("="*80)
        
        for i, exec in enumerate(executions, 1):
            max_comp = exec.input_data.get("max_competitors", 10)
            competitors = exec.output_data.get("competitors", []) if exec.output_data else []
            print(f"{i}. Date: {exec.start_time}")
            print(f"   max_competitors: {max_comp}")
            print(f"   Concurrents trouvés: {len(competitors)}")
            print()
        
        # Prendre la plus récente avec max_competitors=35
        latest_35 = None
        for exec in executions:
            if exec.input_data.get("max_competitors") == 35:
                latest_35 = exec
                break
        
        if not latest_35:
            print("❌ Aucune recherche avec max_competitors=35 trouvée")
            return
        
        print("="*80)
        print("ANALYSE DE LA RECHERCHE AVEC max_competitors=35")
        print("="*80)
        print(f"Date: {latest_35.start_time}")
        print(f"Execution ID: {latest_35.execution_id}\n")
        
        output_data = latest_35.output_data
        competitors = output_data.get("competitors", [])
        excluded_candidates = output_data.get("excluded_candidates", [])
        total_found = output_data.get("total_found", 0)
        total_evaluated = output_data.get("total_evaluated", 0)
        
        print(f"📊 STATISTIQUES")
        print("-"*80)
        print(f"Total candidats trouvés: {total_found}")
        print(f"Total candidats évalués: {total_evaluated}")
        print(f"Concurrents inclus: {len(competitors)}")
        print(f"Concurrents exclus: {len(excluded_candidates)}")
        
        # Analyser le scraping
        print(f"\n📰 ANALYSE DU SCRAPING")
        print("-"*80)
        
        validated = [c for c in competitors if c.get("validated", False) or c.get("manual", False)]
        print(f"Concurrents validés: {len(validated)}")
        
        scraped_count = 0
        scraping_stats = []
        not_scraped = []
        
        for competitor in validated:
            comp_domain = competitor.get("domain")
            if not comp_domain:
                continue
            
            article_count = await count_competitor_articles(db, domain=comp_domain)
            
            if article_count > 0:
                scraped_count += 1
                similarity = competitor.get("relevance_score", 0) * 100 if competitor.get("relevance_score") else 0
                scraping_stats.append({
                    "domain": comp_domain,
                    "articles": article_count,
                    "similarity": similarity
                })
            else:
                similarity = competitor.get("relevance_score", 0) * 100 if competitor.get("relevance_score") else 0
                not_scraped.append({
                    "domain": comp_domain,
                    "similarity": similarity
                })
        
        print(f"Concurrents scrapés: {scraped_count}/{len(validated)} ({scraped_count/len(validated)*100:.1f}%)" if validated else "0/0")
        
        total_articles = sum(s["articles"] for s in scraping_stats)
        print(f"Total articles scrapés: {total_articles}")
        
        if scraping_stats:
            avg_articles = total_articles / len(scraping_stats)
            print(f"Moyenne articles par concurrent scrapé: {avg_articles:.1f}")
        
        # Liste des concurrents
        print(f"\n✅ CONCURRENTS INCLUS ({len(competitors)})")
        print("-"*80)
        print("Top 35 concurrents:")
        for i, comp in enumerate(competitors, 1):
            domain_name = comp.get("domain", "N/A")
            similarity = comp.get("relevance_score", 0) * 100 if comp.get("relevance_score") else 0
            validated_marker = "✓" if (comp.get("validated", False) or comp.get("manual", False)) else " "
            scraped_marker = "📰" if any(s["domain"] == domain_name for s in scraping_stats) else "  "
            print(f"{i:2d}. {domain_name:<45} {similarity:5.1f}% {validated_marker} {scraped_marker}")
        
        # Comparaison avec ancienne config
        print(f"\n" + "="*80)
        print("COMPARAISON AVEC L'ANCIENNE CONFIGURATION")
        print("="*80)
        print(f"Ancienne config (max_competitors=10):")
        print(f"  - Concurrents inclus: 10")
        print(f"  - Concurrents exclus: 140")
        print(f"  - Concurrents scrapés: 8/10 (80%)")
        print(f"  - Articles scrapés: 418")
        print(f"\nNouvelle config (max_competitors=35):")
        print(f"  - Concurrents inclus: {len(competitors)}")
        print(f"  - Concurrents exclus: {len(excluded_candidates)}")
        print(f"  - Concurrents scrapés: {scraped_count}/{len(validated)} ({scraped_count/len(validated)*100:.1f}%)" if validated else f"  - Concurrents scrapés: 0/0")
        print(f"  - Articles scrapés: {total_articles}")
        print(f"\n📈 Amélioration:")
        print(f"  - +{len(competitors) - 10} concurrents inclus (+{(len(competitors) - 10) / 10 * 100:.0f}%)")
        print(f"  - {len(excluded_candidates)} exclus (vs 140 avant)")
        print(f"  - {total_articles} articles scrapés (vs 418 avant)")
        print("="*80)


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    asyncio.run(analyze_latest_35(domain))


