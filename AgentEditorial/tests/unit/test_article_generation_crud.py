import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.crud_generated_articles import create_article, list_articles


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_and_list_articles(db_session: AsyncSession) -> None:
    article = await create_article(
        db_session,
        topic="Test topic for article generation",
        keywords=["test", "article"],
        tone="professional",
        target_words=1500,
        language="fr",
    )
    await db_session.commit()

    articles = await list_articles(db_session)

    assert any(a.id == article.id for a in articles)











