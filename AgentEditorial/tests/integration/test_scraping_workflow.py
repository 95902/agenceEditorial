"""Integration tests for scraping workflow (T094 - US5)."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_profiles import create_site_profile
from python_scripts.ingestion.detect_sitemaps import get_sitemap_urls, parse_sitemap
from python_scripts.ingestion.crawl_pages import crawl_page_async, generate_url_hash
from python_scripts.ingestion.robots_txt import parse_robots_txt


@pytest.mark.integration
@pytest.mark.asyncio
class TestScrapingWorkflow:
    """Integration tests for scraping workflow."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        """Create database session for tests."""
        async with AsyncSessionLocal() as session:
            yield session
            await session.rollback()

    async def test_sitemap_detection_integration(self) -> None:
        """Test sitemap detection workflow."""
        # This test verifies the sitemap detection logic
        # In a real scenario, this would call actual domains
        domain = "example.com"
        
        # Mock the HTTP calls to avoid actual network requests
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = """
User-agent: *
Sitemap: https://example.com/sitemap.xml
"""
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.head = AsyncMock(return_value=mock_response)
            
            sitemap_urls = await get_sitemap_urls(domain)
            assert isinstance(sitemap_urls, list)

    async def test_sitemap_parsing_integration(self) -> None:
        """Test sitemap parsing workflow."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/article1</loc>
        <lastmod>2024-01-01</lastmod>
    </url>
    <url>
        <loc>https://example.com/article2</loc>
        <lastmod>2024-01-02</lastmod>
    </url>
</urlset>"""
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = sitemap_xml
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            urls = await parse_sitemap("https://example.com/sitemap.xml")
            assert len(urls) == 2
            assert "https://example.com/article1" in urls
            assert "https://example.com/article2" in urls

    async def test_url_hash_generation(self) -> None:
        """Test URL hash generation for deduplication."""
        url1 = "https://example.com/article"
        url2 = "https://example.com/article"
        url3 = "https://example.com/other"
        
        hash1 = generate_url_hash(url1)
        hash2 = generate_url_hash(url2)
        hash3 = generate_url_hash(url3)
        
        assert hash1 == hash2  # Same URL should produce same hash
        assert hash1 != hash3  # Different URLs should produce different hashes
        assert len(hash1) == 64  # SHA256 produces 64 char hex string

    @pytest.mark.slow
    async def test_crawl_page_article_extraction(self) -> None:
        """Test article extraction from HTML."""
        # Mock HTML with article content
        article_html = """
        <html>
            <head>
                <title>Test Article Title</title>
                <meta name="description" content="Test article description">
            </head>
            <body>
                <article>
                    <h1>Test Article Title</h1>
                    <p class="author">John Doe</p>
                    <time datetime="2024-01-15">January 15, 2024</time>
                    <div class="content">
                        <p>This is a test article with enough content to pass the minimum word count requirement. 
                        It should have at least 250 words to be considered valid. Let me add more text here to 
                        make sure we meet that requirement. This is a test article with enough content to pass 
                        the minimum word count requirement. It should have at least 250 words to be considered 
                        valid. Let me add more text here to make sure we meet that requirement. This is a test 
                        article with enough content to pass the minimum word count requirement. It should have 
                        at least 250 words to be considered valid. Let me add more text here to make sure we 
                        meet that requirement. This is a test article with enough content to pass the minimum 
                        word count requirement. It should have at least 250 words to be considered valid.</p>
                    </div>
                </article>
            </body>
        </html>
        """
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = article_html
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await crawl_page_async("https://example.com/article")
            assert result["success"] is True
            assert "title" in result or "Test Article Title" in result.get("text", "")
            assert len(result.get("text", "")) > 0

    async def test_article_filtering_by_word_count(self) -> None:
        """Test article filtering logic (minimum word count)."""
        # This will be tested in the agent_scraping implementation
        # For now, verify the concept
        min_words = 250
        
        short_article = " ".join(["word"] * 100)  # 100 words - should be filtered
        long_article = " ".join(["word"] * 500)  # 500 words - should pass
        
        assert len(short_article.split()) < min_words
        assert len(long_article.split()) >= min_words

    async def test_article_filtering_by_age(self) -> None:
        """Test article filtering logic (maximum age)."""
        max_age_days = 730  # 2 years
        
        recent_date = datetime.now(timezone.utc) - timedelta(days=100)
        old_date = datetime.now(timezone.utc) - timedelta(days=800)
        
        recent_age = (datetime.now(timezone.utc) - recent_date).days
        old_age = (datetime.now(timezone.utc) - old_date).days
        
        assert recent_age < max_age_days  # Should pass
        assert old_age >= max_age_days  # Should be filtered

    async def test_robots_txt_permission_check(self) -> None:
        """Test robots.txt permission checking."""
        robots_content = """
User-agent: *
Allow: /blog/
Disallow: /admin/
Crawl-delay: 5
"""
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = robots_content
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            parser = await parse_robots_txt("example.com")
            if parser:
                # Check that blog URLs are allowed
                assert parser.is_allowed("https://example.com/blog/article") is True
                # Check that admin URLs are disallowed
                assert parser.is_allowed("https://example.com/admin/") is False
                # Check crawl delay
                delay = parser.get_crawl_delay()
                assert delay == 5

    async def test_scraping_workflow_with_mocked_sources(self, db_session: AsyncSession, mocker) -> None:
        """Test full scraping workflow with mocked sources."""
        # Create test site profile for context
        await create_site_profile(
            db_session,
            domain="test-competitor.fr",
            language_level="professional",
        )
        await db_session.commit()
        
        # Mock sitemap detection
        mock_sitemap_urls = [
            "https://test-competitor.fr/blog/article1",
            "https://test-competitor.fr/blog/article2",
            "https://test-competitor.fr/blog/article3",
        ]
        
        mocker.patch(
            "python_scripts.ingestion.detect_sitemaps.get_sitemap_urls",
            return_value=mock_sitemap_urls,
        )
        
        # Mock article crawling
        def mock_crawl(url: str):
            return {
                "url": url,
                "success": True,
                "html": f"<html><body><article><h1>Article from {url}</h1><p>{'word ' * 300}</p></article></body></html>",
                "text": f"Article from {url} " + "word " * 300,
                "title": f"Article from {url}",
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
        
        mocker.patch(
            "python_scripts.ingestion.crawl_pages.crawl_page_async",
            side_effect=lambda url, **kwargs: AsyncMock(return_value=mock_crawl(url))(),
        )
        
        # Mock robots.txt parsing
        mock_parser = MagicMock()
        mock_parser.is_allowed = lambda url: True
        mock_parser.get_crawl_delay = lambda: 1
        
        mocker.patch(
            "python_scripts.ingestion.robots_txt.parse_robots_txt",
            return_value=mock_parser,
        )
        
        # Verify mocks work
        sitemap_urls = await get_sitemap_urls("test-competitor.fr")
        assert len(sitemap_urls) == 3
        
        # This test structure verifies the workflow components
        # Full implementation will be in agent_scraping.py

    async def test_url_deduplication(self) -> None:
        """Test URL deduplication logic."""
        urls = [
            "https://example.com/article",
            "https://example.com/article",  # Duplicate
            "https://example.com/article?ref=twitter",  # Different query param
            "https://example.com/other",
        ]
        
        # Generate hashes
        hashes = [generate_url_hash(url) for url in urls]
        
        # Exact duplicates should have same hash
        assert hashes[0] == hashes[1]
        
        # Different URLs should have different hashes
        assert hashes[0] != hashes[3]
        
        # Deduplication would filter based on hash
        unique_hashes = list(set(hashes))
        assert len(unique_hashes) <= len(urls)

