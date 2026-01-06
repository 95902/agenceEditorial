#!/usr/bin/env python3
"""Vérifie la dernière recherche et relance si nécessaire avec max_competitors=35"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.database.crud_executions import create_workflow_execution, update_workflow_execution


async def check_last_search(domain: str):
    """Vérifie la dernière recherche."""
    async with AsyncSessionLocal() as db:
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
        
        if execution:
            max_comp = execution.input_data.get("max_competitors", 10)
            competitors_count = len(execution.output_data.get("competitors", [])) if execution.output_data else 0
            
            print(f"📊 Dernière recherche trouvée:")
            print(f"   Date: {execution.start_time}")
            print(f"   max_competitors utilisé: {max_comp}")
            print(f"   Concurrents trouvés: {competitors_count}")
            
            return max_comp, execution.start_time
        else:
            print("❌ Aucune recherche trouvée")
            return None, None


async def relaunch_with_35(domain: str):
    """Relance la recherche avec max_competitors=35."""
    print(f"\n🚀 Relance de la recherche avec max_competitors=35...\n")
    
    async with AsyncSessionLocal() as db:
        execution = await create_workflow_execution(
            db,
            workflow_type="competitor_search",
            input_data={
                "domain": domain,
                "max_competitors": 35,  # Forcer à 35
            },
            status="pending",
        )
        
        execution_id = execution.execution_id
        print(f"✅ Exécution créée: {execution_id}")
        
        agent = CompetitorSearchAgent()
        
        try:
            await update_workflow_execution(db, execution, status="running")
            
            # Exécuter avec max_competitors=35 explicitement
            complete_results = await agent.execute(
                execution_id=execution_id,
                input_data={
                    "domain": domain,
                    "max_competitors": 35,  # Forcer à 35
                },
                db_session=db,
            )
            
            await db.commit()
            
            results = complete_results.get("competitors", [])
            print(f"\n✅ Recherche terminée !")
            print(f"   {len(results)} concurrents trouvés\n")
            
            return results
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            await update_workflow_execution(db, execution, status="failed", was_success=False)
            await db.commit()
            return None


async def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    
    print("="*80)
    print("VÉRIFICATION ET RELANCE")
    print("="*80)
    
    max_comp, last_date = await check_last_search(domain)
    
    if max_comp is None or max_comp < 35:
        print(f"\n⚠️ La dernière recherche avait max_competitors={max_comp if max_comp else 'N/A'}")
        print("   Relance nécessaire avec max_competitors=35\n")
        
        results = await relaunch_with_35(domain)
        
        if results:
            print("="*80)
            print("RÉSULTATS")
            print("="*80)
            print(f"Nombre de concurrents: {len(results)}")
            print(f"\nListe:")
            for i, comp in enumerate(results, 1):
                domain_name = comp.get("domain", "N/A")
                similarity = comp.get("relevance_score", 0) * 100 if comp.get("relevance_score") else 0
                print(f"{i:2d}. {domain_name:<45} {similarity:5.1f}%")
    else:
        print(f"\n✅ La dernière recherche avait déjà max_competitors={max_comp}")
        print("   Pas besoin de relancer")


if __name__ == "__main__":
    asyncio.run(main())


