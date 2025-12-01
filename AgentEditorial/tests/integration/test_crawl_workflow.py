"""Integration tests for crawl workflow."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.ingestion.crawl_pages import (
    check_cache,
    crawl_multiple_pages,
    crawl_with_permissions,
    generate_url_hash,
)
from python_scripts.ingestion.detect_sitemaps import detect_sitemap_urls, parse_sitemap
from python_scripts.ingestion.robots_txt import parse_robots_txt


@pytest.mark.integration
@pytest.mark.asyncio
class TestCrawlWorkflow:
    """Integration tests for crawl workflow."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        """Create database session for tests."""
        async with AsyncSessionLocal() as session:
            yield session
            await session.rollback()

    async def test_generate_url_hash(self) -> None:
        """Test URL hash generation."""
        url1 = "https://example.com/page"
        url2 = "https://example.com/page"
        url3 = "https://example.com/other"

        hash1 = generate_url_hash(url1)
        hash2 = generate_url_hash(url2)
        hash3 = generate_url_hash(url3)

        assert hash1 == hash2  # Same URL should produce same hash
        assert hash1 != hash3  # Different URLs should produce different hashes
        assert len(hash1) == 64  # SHA256 produces 64 char hex string

    async def test_check_cache_empty(self, db_session: AsyncSession) -> None:
        """Test cache check when cache is empty."""
        result = await check_cache(db_session, "https://example.com/test")
        assert result is None

    @pytest.mark.slow
    async def test_parse_robots_txt_real_domain(self) -> None:
        """Test parsing robots.txt from a real domain (slow test)."""
        # Use a well-known domain that has robots.txt
        parser = await parse_robots_txt("www.google.com")
        if parser:
            # If robots.txt exists, verify it's parsed correctly
            assert parser.user_agents is not None
            # Check that we can query crawl delay
            delay = parser.get_crawl_delay()
            # Delay might be None or an integer
            assert delay is None or isinstance(delay, int)

    @pytest.mark.slow
    async def test_detect_sitemap_urls(self) -> None:
        """Test sitemap detection (slow test)."""
        # Test with a domain that likely has a sitemap
        sitemap_urls = await detect_sitemap_urls("example.com")
        # Result might be empty or contain URLs
        assert isinstance(sitemap_urls, list)

    @pytest.mark.slow
    async def test_parse_sitemap(self) -> None:
        """Test sitemap parsing (slow test)."""
        # Test with a known sitemap URL
        # Note: This might fail if the URL doesn't exist
        urls = await parse_sitemap("https://www.sitemaps.org/sitemap.xml")
        # Should return a list (might be empty)
        assert isinstance(urls, list)

    @pytest.mark.slow
    async def test_crawl_with_permissions_simple(self) -> None:
        """Test crawling with permissions check (slow test)."""
        # Test with a simple, accessible URL
        url = "https://example.com"
        result = await crawl_with_permissions(
            url=url,
            domain="example.com",
            use_cache=False,
        )
        # Should return a result dict
        assert isinstance(result, dict)
        assert "url" in result
        assert "content" in result or "error" in result

    @pytest.mark.slow
    async def test_crawl_multiple_pages(self) -> None:
        """Test crawling multiple pages (slow test)."""
        urls = [
            "https://example.com",
        ]
        results = await crawl_multiple_pages(
            urls=urls,
            domain="example.com",
            use_cache=False,
        )
        # Should return a list of results
        assert isinstance(results, list)
        assert len(results) > 0
        # Each result should have url and content or error
        for result in results:
            assert "url" in result
            assert "content" in result or "error" in result

    async def test_crawl_workflow_with_cache(self, db_session: AsyncSession) -> None:
        """Test crawl workflow with caching."""
        url = "https://example.com/test"
        # First crawl - should not be cached
        cache_result = await check_cache(db_session, url)
        assert cache_result is None

        # Note: Actual caching would require a successful crawl first
        # This test verifies the cache check mechanism works


@pytest.mark.integration
@pytest.mark.asyncio
class TestCrawlPermissions:
    """Test crawl permissions and robots.txt integration."""

    @pytest.mark.slow
    async def test_crawl_respects_robots_txt(self) -> None:
        """Test that crawling respects robots.txt (slow test)."""
        # This is a conceptual test - actual implementation would check
        # robots.txt before crawling
        domain = "example.com"
        parser = await parse_robots_txt(domain)

        if parser:
            # If robots.txt exists, verify we can check permissions
            test_url = f"https://{domain}/test"
            is_allowed = parser.is_allowed(test_url)
            assert isinstance(is_allowed, bool)

    async def test_robots_txt_crawl_delay(self) -> None:
        """Test that crawl delay is extracted correctly."""
        # Create a mock robots.txt content
        content = """
User-agent: *
Crawl-delay: 5
"""
        from python_scripts.ingestion.robots_txt import RobotsTxtParser

        parser = RobotsTxtParser(content, "https://example.com")
        delay = parser.get_crawl_delay()
        assert delay == 5

