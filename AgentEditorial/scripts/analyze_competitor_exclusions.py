#!/usr/bin/env python3
"""
Analyse détaillée des exclusions de concurrents

Ce script explique pourquoi seulement 10 candidats sont inclus et pourquoi 140 sont exclus.
"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution


async def analyze_exclusions(domain: str = "innosys.fr"):
    """Analyse les exclusions de concurrents."""
    async with AsyncSessionLocal() as db:
        # Récupérer la dernière exécution
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
        
        output_data = execution.output_data
        
        # Statistiques générales
        total_found = output_data.get("total_found", 0)
        total_evaluated = output_data.get("total_evaluated", 0)
        competitors = output_data.get("competitors", [])
        all_candidates = output_data.get("all_candidates", [])
        excluded_candidates = output_data.get("excluded_candidates", [])
        
        print("="*80)
        print(f"ANALYSE DES EXCLUSIONS - {domain}")
        print("="*80)
        
        print(f"\n📊 STATISTIQUES GÉNÉRALES")
        print("-"*80)
        print(f"Total de candidats trouvés initialement: {total_found}")
        print(f"Total de candidats évalués: {total_evaluated}")
        print(f"Concurrents inclus (final): {len(competitors)}")
        print(f"Concurrents exclus: {len(excluded_candidates)}")
        
        # Analyser les raisons d'exclusion
        if excluded_candidates:
            print(f"\n🔍 ANALYSE DES RAISONS D'EXCLUSION")
            print("-"*80)
            
            exclusion_reasons = Counter()
            exclusion_by_category = Counter()
            exclusion_details = []
            
            for candidate in excluded_candidates:
                reason = candidate.get("exclusion_reason", "Unknown")
                exclusion_reasons[reason] += 1
                
                # Catégoriser les exclusions
                if "diversity" in reason.lower() or "category limit" in reason.lower():
                    exclusion_by_category["Diversité/Catégorie"] += 1
                elif "confidence" in reason.lower():
                    exclusion_by_category["Confiance trop faible"] += 1
                elif "combined score" in reason.lower():
                    exclusion_by_category["Score combiné trop faible"] += 1
                elif "ranking" in reason.lower() or "threshold" in reason.lower():
                    exclusion_by_category["Seuil de classement"] += 1
                else:
                    exclusion_by_category["Autre"] += 1
                
                exclusion_details.append({
                    "domain": candidate.get("domain", "N/A"),
                    "reason": reason,
                    "relevance_score": candidate.get("relevance_score", 0),
                    "confidence_score": candidate.get("confidence_score", 0),
                    "combined_score": candidate.get("combined_score", 0),
                    "final_confidence": candidate.get("final_confidence", 0)
                })
            
            print(f"\nRépartition par catégorie d'exclusion:")
            for category, count in exclusion_by_category.most_common():
                percentage = (count / len(excluded_candidates)) * 100
                print(f"  {category}: {count} ({percentage:.1f}%)")
            
            print(f"\nTop 10 raisons d'exclusion:")
            for reason, count in exclusion_reasons.most_common(10):
                percentage = (count / len(excluded_candidates)) * 100
                print(f"  {reason}: {count} ({percentage:.1f}%)")
            
            # Analyser les scores des exclus
            print(f"\n📈 ANALYSE DES SCORES DES EXCLUS")
            print("-"*80)
            
            relevance_scores = [c.get("relevance_score", 0) for c in excluded_candidates if c.get("relevance_score")]
            confidence_scores = [c.get("confidence_score", 0) for c in excluded_candidates if c.get("confidence_score")]
            combined_scores = [c.get("combined_score", 0) for c in excluded_candidates if c.get("combined_score")]
            final_confidences = [c.get("final_confidence", 0) for c in excluded_candidates if c.get("final_confidence")]
            
            if relevance_scores:
                print(f"Relevance Score:")
                print(f"  Moyenne: {sum(relevance_scores)/len(relevance_scores):.3f}")
                print(f"  Min: {min(relevance_scores):.3f}, Max: {max(relevance_scores):.3f}")
            
            if confidence_scores:
                print(f"Confidence Score:")
                print(f"  Moyenne: {sum(confidence_scores)/len(confidence_scores):.3f}")
                print(f"  Min: {min(confidence_scores):.3f}, Max: {max(confidence_scores):.3f}")
            
            if combined_scores:
                print(f"Combined Score:")
                print(f"  Moyenne: {sum(combined_scores)/len(combined_scores):.3f}")
                print(f"  Min: {min(combined_scores):.3f}, Max: {max(combined_scores):.3f}")
            
            if final_confidences:
                print(f"Final Confidence:")
                print(f"  Moyenne: {sum(final_confidences)/len(final_confidences):.3f}")
                print(f"  Min: {min(final_confidences):.3f}, Max: {max(final_confidences):.3f}")
            
            # Comparer avec les inclus
            print(f"\n📊 COMPARAISON INCLUS vs EXCLUS")
            print("-"*80)
            
            included_relevance = [c.get("relevance_score", 0) for c in competitors if c.get("relevance_score")]
            included_combined = [c.get("combined_score", 0) for c in competitors if c.get("combined_score")]
            included_final_conf = [c.get("final_confidence", 0) for c in competitors if c.get("final_confidence")]
            
            if included_relevance and relevance_scores:
                print(f"Relevance Score moyen:")
                print(f"  Inclus: {sum(included_relevance)/len(included_relevance):.3f}")
                print(f"  Exclus: {sum(relevance_scores)/len(relevance_scores):.3f}")
            
            if included_combined and combined_scores:
                print(f"Combined Score moyen:")
                print(f"  Inclus: {sum(included_combined)/len(included_combined):.3f}")
                print(f"  Exclus: {sum(combined_scores)/len(combined_scores):.3f}")
            
            if included_final_conf and final_confidences:
                print(f"Final Confidence moyen:")
                print(f"  Inclus: {sum(included_final_conf)/len(included_final_conf):.3f}")
                print(f"  Exclus: {sum(final_confidences)/len(final_confidences):.3f}")
        
        # Analyser le pipeline de filtrage
        print(f"\n🔧 PIPELINE DE FILTRAGE")
        print("-"*80)
        
        # Vérifier s'il y a des informations sur les étapes
        pipeline_info = output_data.get("pipeline_steps", {})
        if pipeline_info:
            print("Étapes du pipeline:")
            for step, count in pipeline_info.items():
                print(f"  {step}: {count} candidats")
        
        # Expliquer pourquoi seulement 10
        print(f"\n💡 EXPLICATION")
        print("-"*80)
        print(f"Pourquoi seulement {len(competitors)} concurrents inclus ?")
        print(f"\n1. Limite maximale: Le paramètre max_competitors est fixé à 10")
        print(f"   (voir ligne 655 dans agent.py: final_competitors[:max_competitors])")
        print(f"\n2. Filtrage strict: Le pipeline applique plusieurs filtres:")
        print(f"   - Filtrage LLM (relevance_score >= 0.6 requis)")
        print(f"   - Validation du contenu")
        print(f"   - Assurance de diversité (max par catégorie)")
        print(f"   - Scores minimaux requis:")
        print(f"     * min_confidence_score: 0.35")
        print(f"     * min_combined_score: 0.35")
        print(f"\n3. Classement final: Seuls les meilleurs candidats sont retenus")
        print(f"   après calcul des scores combinés (LLM + similarité sémantique)")
        print(f"\n4. Les 140 exclus ont été filtrés car:")
        print(f"   - Scores trop faibles (confiance ou score combiné < seuils)")
        print(f"   - Limite de diversité atteinte (max par catégorie)")
        print(f"   - Classement insuffisant (en dessous du top 10)")
        
        print("\n" + "="*80)


async def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyse des exclusions de concurrents"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)"
    )
    
    args = parser.parse_args()
    
    await analyze_exclusions(args.domain)


if __name__ == "__main__":
    asyncio.run(main())


