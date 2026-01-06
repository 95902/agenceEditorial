#!/usr/bin/env python3
"""Vérifie l'exécution en cours et récupère les résultats si disponibles"""

import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.database.crud_executions import get_workflow_execution


async def check_running(execution_id: str):
    """Vérifie une exécution spécifique."""
    async with AsyncSessionLocal() as db:
        execution = await get_workflow_execution(db, execution_id)
        
        if not execution:
            print(f"❌ Exécution {execution_id} non trouvée")
            return
        
        print("="*80)
        print(f"EXÉCUTION: {execution_id}")
        print("="*80)
        print(f"Status: {execution.status}")
        print(f"Date début: {execution.start_time}")
        print(f"Date fin: {execution.end_time}")
        print(f"max_competitors: {execution.input_data.get('max_competitors', 'N/A')}")
        
        if execution.output_data:
            competitors = execution.output_data.get("competitors", [])
            total_found = execution.output_data.get("total_found", 0)
            total_evaluated = execution.output_data.get("total_evaluated", 0)
            excluded = execution.output_data.get("excluded_candidates", [])
            
            print(f"\n📊 RÉSULTATS")
            print("-"*80)
            print(f"Concurrents trouvés: {len(competitors)}")
            print(f"Total trouvés: {total_found}")
            print(f"Total évalués: {total_evaluated}")
            print(f"Exclus: {len(excluded)}")
            
            if competitors:
                print(f"\n✅ LISTE DES {len(competitors)} CONCURRENTS")
                print("-"*80)
                for i, comp in enumerate(competitors, 1):
                    domain_name = comp.get("domain", "N/A")
                    similarity = comp.get("relevance_score", 0) * 100 if comp.get("relevance_score") else 0
                    validated = "✓" if (comp.get("validated", False) or comp.get("manual", False)) else " "
                    print(f"{i:2d}. {domain_name:<45} {similarity:5.1f}% {validated}")
        else:
            print("\n⚠️ Aucun output_data disponible")
        
        # Si status est "running" mais qu'on a des résultats, on peut forcer le statut à "completed"
        if execution.status == "running" and execution.output_data and execution.output_data.get("competitors"):
            print(f"\n💡 L'exécution est en 'running' mais a des résultats.")
            print(f"   On peut la marquer comme 'completed' si vous voulez.")
        
        print("="*80)


if __name__ == "__main__":
    exec_id = sys.argv[1] if len(sys.argv) > 1 else "2417bc85-cf1a-491d-acf3-e77e837c9a03"
    asyncio.run(check_running(exec_id))


