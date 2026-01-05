"""Script pour déboguer l'exécution 115 et voir pourquoi total_found est None."""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.database.crud_topics import make_json_serializable

async def debug_execution():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.id == 115)
        )
        exec = result.scalar_one_or_none()
        
        if not exec:
            print("Exécution 115 non trouvée")
            return
        
        print("=" * 80)
        print("ANALYSE DE L'EXÉCUTION 115")
        print("=" * 80)
        print(f"Status: {exec.status}")
        print(f"Has output_data: {exec.output_data is not None}")
        
        if exec.output_data:
            print("\nChamps dans output_data:")
            for key in exec.output_data.keys():
                value = exec.output_data[key]
                value_type = type(value).__name__
                if isinstance(value, (list, dict)):
                    print(f"  - {key}: {value_type} (len={len(value)})")
                else:
                    print(f"  - {key}: {value} (type: {value_type})")
            
            # Test de make_json_serializable sur les valeurs
            print("\nTest de make_json_serializable:")
            test_data = {
                "total_found": len(exec.output_data.get("competitors", [])),
                "total_evaluated": len(exec.output_data.get("all_candidates", [])),
            }
            print(f"Avant make_json_serializable: {test_data}")
            serialized = make_json_serializable(test_data)
            print(f"Après make_json_serializable: {serialized}")
            
            # Vérifier si les valeurs sont None dans la DB
            print("\nValeurs dans la DB:")
            print(f"  total_found: {exec.output_data.get('total_found')} (type: {type(exec.output_data.get('total_found'))})")
            print(f"  total_evaluated: {exec.output_data.get('total_evaluated')} (type: {type(exec.output_data.get('total_evaluated'))})")
            
            # Vérifier si les clés existent
            print("\nClés présentes:")
            print(f"  'total_found' in output_data: {'total_found' in exec.output_data}")
            print(f"  'total_evaluated' in output_data: {'total_evaluated' in exec.output_data}")

asyncio.run(debug_execution())



















