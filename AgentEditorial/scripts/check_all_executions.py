#!/usr/bin/env python3
"""Vérifie toutes les exécutions, y compris celles en cours"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution


async def check_all(domain: str = "innosys.fr"):
    """Vérifie toutes les exécutions."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(10)
        )
        
        result = await db.execute(stmt)
        executions = result.scalars().all()
        
        print("="*80)
        print(f"TOUTES LES EXÉCUTIONS POUR {domain}")
        print("="*80)
        
        for i, exec in enumerate(executions, 1):
            max_comp = exec.input_data.get("max_competitors", "N/A")
            status = exec.status
            competitors_count = 0
            if exec.output_data:
                competitors_count = len(exec.output_data.get("competitors", []))
            
            print(f"\n{i}. Execution ID: {exec.execution_id}")
            print(f"   Date: {exec.start_time}")
            print(f"   Status: {status}")
            print(f"   max_competitors: {max_comp}")
            print(f"   Concurrents trouvés: {competitors_count}")
            
            if exec.output_data and exec.status == "completed":
                total_found = exec.output_data.get("total_found", 0)
                total_evaluated = exec.output_data.get("total_evaluated", 0)
                excluded = exec.output_data.get("excluded_candidates", [])
                print(f"   Total trouvés: {total_found}")
                print(f"   Total évalués: {total_evaluated}")
                print(f"   Exclus: {len(excluded)}")
        
        print("\n" + "="*80)


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    asyncio.run(check_all(domain))


