#!/usr/bin/env python3
"""
Génère un fichier JSON d'analyse complète de l'audit avec les données des concurrents scrapés
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.database.crud_articles import count_competitor_articles


async def generate_complete_analysis(domain: str = "innosys.fr") -> Dict[str, Any]:
    """Génère une analyse complète."""
    async with AsyncSessionLocal() as db:
        # 1. Récupérer la dernière recherche de concurrents
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
            return {
                "error": "Aucune recherche de concurrents trouvée",
                "domain": domain
            }
        
        output_data = execution.output_data
        competitors_data = output_data.get("competitors", [])
        excluded_candidates = output_data.get("excluded_candidates", [])
        max_competitors_requested = execution.input_data.get("max_competitors", 10)
        
        # 2. Analyser le scraping
        validated_competitors = [
            c for c in competitors_data
            if c.get("validated", False) or c.get("manual", False)
        ]
        
        scraped_stats = []
        not_scraped_list = []
        
        for competitor in validated_competitors:
            comp_domain = competitor.get("domain")
            if not comp_domain:
                continue
            
            article_count = await count_competitor_articles(db, domain=comp_domain)
            similarity = competitor.get("relevance_score", 0) * 100 if competitor.get("relevance_score") else 0
            
            if article_count > 0:
                scraped_stats.append({
                    "domain": comp_domain,
                    "articles_count": article_count,
                    "similarity": round(similarity, 1),
                    "validated": True
                })
            else:
                not_scraped_list.append({
                    "domain": comp_domain,
                    "similarity": round(similarity, 1),
                    "validated": True
                })
        
        # 3. Calculer les statistiques
        total_articles = sum(s["articles_count"] for s in scraped_stats)
        avg_articles = total_articles / len(scraped_stats) if scraped_stats else 0
        
        # 4. Construire l'analyse complète
        analysis = {
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "complete_audit_analysis",
            
            "competitor_search": {
                "execution_id": str(execution.execution_id),
                "search_date": execution.start_time.isoformat() if execution.start_time else None,
                "max_competitors_requested": max_competitors_requested,
                "total_candidates_found": output_data.get("total_found", len(competitors_data)),
                "total_candidates_evaluated": output_data.get("total_evaluated", 0),
                "competitors_included": len(competitors_data),
                "competitors_excluded": len(excluded_candidates),
                "competitors_validated": len(validated_competitors),
            },
            
            "scraping_analysis": {
                "total_competitors": len(validated_competitors),
                "scraped_count": len(scraped_stats),
                "not_scraped_count": len(not_scraped_list),
                "scraping_rate": round(len(scraped_stats) / len(validated_competitors) * 100, 1) if validated_competitors else 0,
                "total_articles_scraped": total_articles,
                "avg_articles_per_competitor": round(avg_articles, 1),
                "min_articles": min(s["articles_count"] for s in scraped_stats) if scraped_stats else 0,
                "max_articles": max(s["articles_count"] for s in scraped_stats) if scraped_stats else 0,
            },
            
            "scraped_competitors": sorted(scraped_stats, key=lambda x: x["articles_count"], reverse=True),
            "not_scraped_competitors": sorted(not_scraped_list, key=lambda x: x["similarity"], reverse=True),
            
            "exclusion_analysis": {
                "total_excluded": len(excluded_candidates),
                "exclusion_reasons": {}
            },
            
            "recommendations": []
        }
        
        # Analyser les exclusions
        if excluded_candidates:
            from collections import Counter
            exclusion_reasons = Counter()
            for candidate in excluded_candidates:
                reason = candidate.get("exclusion_reason", "Unknown")
                exclusion_reasons[reason] += 1
            
            analysis["exclusion_analysis"]["exclusion_reasons"] = dict(exclusion_reasons)
        
        # Générer des recommandations
        if len(not_scraped_list) > 0:
            high_similarity_not_scraped = [c for c in not_scraped_list if c["similarity"] >= 85]
            if high_similarity_not_scraped:
                analysis["recommendations"].append(
                    f"🔴 {len(high_similarity_not_scraped)} concurrent(s) à haute similarité (≥85%) ne sont pas scrapés. Prioriser leur scraping."
                )
            
            analysis["recommendations"].append(
                f"📰 {len(not_scraped_list)} concurrent(s) ne sont pas encore scrapés. Lancer le scraping pour enrichir les données."
            )
        
        if analysis["scraping_analysis"]["scraping_rate"] < 70:
            analysis["recommendations"].append(
                f"⚠️ Taux de scraping faible ({analysis['scraping_analysis']['scraping_rate']}%). Améliorer le processus de scraping."
            )
        
        if max_competitors_requested == 10:
            analysis["recommendations"].append(
                "💡 max_competitors est à 10. Considérer augmenter à 35 ou plus pour avoir plus de concurrents."
            )
        
        return analysis


async def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Génère un fichier JSON d'analyse complète de l'audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/analysis/audit_output_analysis.json",
        help="Fichier de sortie (défaut: outputs/analysis/audit_output_analysis.json)"
    )
    
    args = parser.parse_args()
    
    print(f"🔍 Génération de l'analyse complète pour {args.domain}...")
    
    analysis = await generate_complete_analysis(args.domain)
    
    # Sauvegarder
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"✅ Analyse sauvegardée: {output_path}")
    print(f"\n📊 Résumé:")
    print(f"   - Concurrents inclus: {analysis.get('competitor_search', {}).get('competitors_included', 0)}")
    print(f"   - Concurrents scrapés: {analysis.get('scraping_analysis', {}).get('scraped_count', 0)}")
    print(f"   - Articles scrapés: {analysis.get('scraping_analysis', {}).get('total_articles_scraped', 0)}")


if __name__ == "__main__":
    asyncio.run(main())

