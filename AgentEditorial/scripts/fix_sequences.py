"""Script to fix PostgreSQL sequence synchronization issues."""

import asyncio
from sqlalchemy import text
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def fix_sequences():
    """Fix PostgreSQL sequences for all tables with auto-increment IDs."""
    async with AsyncSessionLocal() as session:
        try:
            # List of tables with auto-increment IDs
            tables = [
                "workflow_executions",
                "site_profiles",
                "site_analysis_results",
                "competitor_articles",
                "editorial_trends",
                "bertopic_analysis",
                "crawl_cache",
                "scraping_permissions",
                "performance_metrics",
                "audit_log",
            ]
            
            for table in tables:
                # Get the current max ID
                result = await session.execute(
                    text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
                )
                max_id = result.scalar_one()
                
                # Reset the sequence to max_id + 1 (minimum 1 for empty tables)
                sequence_name = f"{table}_id_seq"
                # For empty tables (max_id=0), set to 0 with is_called=false so next value will be 1
                # For non-empty tables, set to max_id with is_called=true so next value will be max_id+1
                if max_id == 0:
                    # Table is empty, reset sequence to start at 1
                    await session.execute(
                        text(f"SELECT setval('{sequence_name}', 1, false)")
                    )
                    next_value = 1
                else:
                    # Table has data, set sequence to max_id so next value is max_id+1
                    await session.execute(
                        text(f"SELECT setval('{sequence_name}', :max_id, true)")
                        .bindparams(max_id=max_id)
                    )
                    next_value = max_id + 1
                
                await session.commit()
                
                logger.info(
                    f"Fixed sequence for {table}",
                    sequence=sequence_name,
                    max_id=max_id,
                    next_value=next_value,
                )
            
            logger.info("All sequences fixed successfully")
            
        except Exception as e:
            logger.error("Failed to fix sequences", error=str(e))
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(fix_sequences())

