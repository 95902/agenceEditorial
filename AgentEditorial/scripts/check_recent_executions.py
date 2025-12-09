"""Script pour trouver les exécutions récentes de competitor_search."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution


async def find_recent_executions():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_type == "competitor_search")
            .where(WorkflowExecution.is_valid == True)  # noqa: E712
            .order_by(desc(WorkflowExecution.created_at))
            .limit(5)
        )
        executions = result.scalars().all()
        
        print("📋 Dernières exécutions de competitor_search:\n")
        for exec in executions:
            print(f"ID: {exec.id}")
            print(f"Execution ID: {exec.execution_id}")
            print(f"Status: {exec.status}")
            print(f"Created: {exec.created_at}")
            print(f"Has output_data: {exec.output_data is not None}")
            if exec.output_data:
                competitors_count = len(exec.output_data.get("competitors", []))
                has_total_found = "total_found" in exec.output_data
                has_total_evaluated = "total_evaluated" in exec.output_data
                has_all_candidates = "all_candidates" in exec.output_data
                has_excluded = "excluded_candidates" in exec.output_data
                print(f"Competitors: {competitors_count}")
                print(f"Has total_found: {has_total_found}")
                print(f"Has total_evaluated: {has_total_evaluated}")
                print(f"Has all_candidates: {has_all_candidates}")
                print(f"Has excluded_candidates: {has_excluded}")
                if has_total_found:
                    print(f"total_found value: {exec.output_data.get('total_found')}")
                if has_total_evaluated:
                    print(f"total_evaluated value: {exec.output_data.get('total_evaluated')}")
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(find_recent_executions())

