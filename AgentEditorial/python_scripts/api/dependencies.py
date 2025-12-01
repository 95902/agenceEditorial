"""FastAPI dependencies for database sessions and rate limiting."""

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import get_db

__all__ = ["get_db_session"]


async def get_db_session() -> AsyncSession:
    """Dependency for FastAPI to get database session."""
    async for session in get_db():
        yield session

