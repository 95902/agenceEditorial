#!/usr/bin/env python3
"""
Relance l'analyse complète directement via Python (sans API)

Ce script lance la recherche de concurrents directement en utilisant les agents.
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.database.crud_executions import create_workflow_execution, update_workflow_execution


async def launch_competitor_search_direct(domain: str, max_competitors: int = 35):
    """Lance la recherche de concurrents directement."""
    print("="*80)
    print("RELANCE DE L'ANALYSE COMPLÈTE")
    print("="*80)
    print(f"Domaine: {domain}")
    print(f"max_competitors: {max_competitors}")
    print("="*80 + "\n")
    
    async with AsyncSessionLocal() as db:
        # Créer une exécution
        execution = await create_workflow_execution(
            db,
            workflow_type="competitor_search",
            input_data={
                "domain": domain,
                "max_competitors": max_competitors,
            },
            status="pending",
        )
        
        execution_id = execution.execution_id
        print(f"✅ Exécution créée: {execution_id}\n")
        
        # Lancer la recherche
        print("🚀 Lancement de la recherche de concurrents...\n")
        
        agent = CompetitorSearchAgent()
        
        try:
            # Mettre à jour le statut
            await update_workflow_execution(
                db,
                execution,
                status="running",
            )
            
            # Exécuter la recherche via execute() pour avoir les métadonnées complètes
            complete_results = await agent.execute(
                execution_id=execution_id,
                input_data={
                    "domain": domain,
                    "max_competitors": max_competitors,
                },
                db_session=db,
            )
            
            # Les résultats sont déjà sauvegardés par execute()
            results = complete_results.get("competitors", [])
            await db.commit()
            
            print("✅ Recherche terminée !\n")
            
            # Analyser les résultats
            print("="*80)
            print("RÉSULTATS")
            print("="*80)
            print(f"Nombre de concurrents trouvés: {len(results)}\n")
            
            if results:
                print("Liste des concurrents:")
                for i, comp in enumerate(results, 1):
                    domain_name = comp.get("domain", "N/A")
                    similarity = comp.get("relevance_score", 0) * 100 if comp.get("relevance_score") else 0
                    validated = comp.get("validated", False) or comp.get("manual", False)
                    validated_marker = "✓" if validated else " "
                    print(f"{i:2d}. {domain_name:<45} {similarity:5.1f}% {validated_marker}")
            
            print("\n" + "="*80)
            
            return results
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            
            await update_workflow_execution(
                db,
                execution,
                status="failed",
                was_success=False,
            )
            await db.commit()
            
            return None


async def main():
    """Point d'entrée principal."""
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    max_competitors = int(sys.argv[2]) if len(sys.argv) > 2 else 35
    
    results = await launch_competitor_search_direct(domain, max_competitors)
    
    if results:
        print(f"\n✅ Analyse terminée avec succès !")
        print(f"   {len(results)} concurrents trouvés avec max_competitors={max_competitors}")
    else:
        print(f"\n❌ Échec de l'analyse")


if __name__ == "__main__":
    asyncio.run(main())

