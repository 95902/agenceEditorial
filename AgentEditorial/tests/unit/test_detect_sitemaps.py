"""Unit tests for sitemap detection (T093 - US5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from python_scripts.ingestion.detect_sitemaps import (
    detect_sitemap_urls,
    get_sitemap_urls,
    parse_sitemap,
)
from python_scripts.utils.exceptions import CrawlingError


@pytest.mark.unit
@pytest.mark.asyncio
class TestDetectSitemapUrls:
    """Test sitemap URL detection."""

    async def test_detect_sitemap_from_robots_txt(self, mocker) -> None:
        """Test detecting sitemap from robots.txt."""
        robots_content = """
User-agent: *
Disallow: /admin/
Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-blog.xml
"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = robots_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            sitemaps = await detect_sitemap_urls("example.com")

        assert len(sitemaps) == 2
        assert "https://example.com/sitemap.xml" in sitemaps
        assert "https://example.com/sitemap-blog.xml" in sitemaps

    async def test_detect_sitemap_common_paths(self, mocker) -> None:
        """Test detecting sitemap from common paths."""
        # Mock robots.txt (no sitemap directive)
        mock_robots_response = MagicMock()
        mock_robots_response.status_code = 200
        mock_robots_response.text = "User-agent: *\nDisallow: /admin/"

        # Mock sitemap.xml (found)
        mock_sitemap_response = MagicMock()
        mock_sitemap_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_robots_response)
        mock_client.head = AsyncMock(return_value=mock_sitemap_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            sitemaps = await detect_sitemap_urls("example.com")

        # Should find at least /sitemap.xml
        assert len(sitemaps) >= 1
        assert any("sitemap.xml" in s for s in sitemaps)

    async def test_detect_sitemap_no_robots_txt(self, mocker) -> None:
        """Test detection when robots.txt is not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            sitemaps = await detect_sitemap_urls("example.com")

        # Should return empty list or try common paths
        assert isinstance(sitemaps, list)

    async def test_detect_sitemap_case_insensitive(self, mocker) -> None:
        """Test that sitemap directive is case-insensitive."""
        robots_content = """
User-agent: *
SITEMAP: https://example.com/sitemap.xml
sitemap: https://example.com/sitemap2.xml
"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = robots_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            sitemaps = await detect_sitemap_urls("example.com")

        assert len(sitemaps) >= 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestParseSitemap:
    """Test sitemap parsing."""

    async def test_parse_regular_sitemap(self, mocker) -> None:
        """Test parsing a regular sitemap."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
        <lastmod>2024-01-01</lastmod>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
        <lastmod>2024-01-02</lastmod>
    </url>
</urlset>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sitemap_xml

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await parse_sitemap("https://example.com/sitemap.xml")

        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    async def test_parse_sitemap_index(self, mocker) -> None:
        """Test parsing a sitemap index."""
        index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
    </sitemap>
    <sitemap>
        <loc>https://example.com/sitemap2.xml</loc>
    </sitemap>
</sitemapindex>"""

        nested_sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/nested-page</loc>
    </url>
</urlset>"""

        # Mock responses: index first, then nested sitemaps
        mock_index_response = MagicMock()
        mock_index_response.status_code = 200
        mock_index_response.text = index_xml

        mock_nested_response = MagicMock()
        mock_nested_response.status_code = 200
        mock_nested_response.text = nested_sitemap_xml

        mock_client = AsyncMock()
        # First call returns index, subsequent calls return nested sitemap
        mock_client.get = AsyncMock(side_effect=[mock_index_response, mock_nested_response, mock_nested_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await parse_sitemap("https://example.com/sitemap_index.xml")

        # Should parse nested sitemaps
        assert len(urls) >= 1
        assert "https://example.com/nested-page" in urls

    async def test_parse_sitemap_not_found(self, mocker) -> None:
        """Test parsing when sitemap is not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CrawlingError):
                await parse_sitemap("https://example.com/sitemap.xml")

    async def test_parse_sitemap_invalid_xml(self, mocker) -> None:
        """Test parsing invalid XML."""
        invalid_xml = "This is not XML"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = invalid_xml

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CrawlingError):
                await parse_sitemap("https://example.com/sitemap.xml")

    async def test_parse_sitemap_empty(self, mocker) -> None:
        """Test parsing empty sitemap."""
        empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = empty_xml

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await parse_sitemap("https://example.com/sitemap.xml")

        assert urls == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetSitemapUrls:
    """Test getting all URLs from sitemaps."""

    async def test_get_sitemap_urls_success(self, mocker) -> None:
        """Test successfully getting URLs from sitemaps."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
    </url>
</urlset>"""

        robots_content = "Sitemap: https://example.com/sitemap.xml"

        mock_robots_response = MagicMock()
        mock_robots_response.status_code = 200
        mock_robots_response.text = robots_content

        mock_sitemap_response = MagicMock()
        mock_sitemap_response.status_code = 200
        mock_sitemap_response.text = sitemap_xml

        mock_client = AsyncMock()
        # First call for robots.txt, second for sitemap
        mock_client.get = AsyncMock(side_effect=[mock_robots_response, mock_sitemap_response])
        mock_client.head = AsyncMock(return_value=MagicMock(status_code=404))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await get_sitemap_urls("example.com")

        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    async def test_get_sitemap_urls_no_sitemaps(self, mocker) -> None:
        """Test when no sitemaps are found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await get_sitemap_urls("example.com")

        assert urls == []

    async def test_get_sitemap_urls_deduplication(self, mocker) -> None:
        """Test that duplicate URLs are removed."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
    </url>
    <url>
        <loc>https://example.com/page1</loc>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
    </url>
</urlset>"""

        robots_content = "Sitemap: https://example.com/sitemap.xml"

        mock_robots_response = MagicMock()
        mock_robots_response.status_code = 200
        mock_robots_response.text = robots_content

        mock_sitemap_response = MagicMock()
        mock_sitemap_response.status_code = 200
        mock_sitemap_response.text = sitemap_xml

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_robots_response, mock_sitemap_response])
        mock_client.head = AsyncMock(return_value=MagicMock(status_code=404))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            urls = await get_sitemap_urls("example.com")

        # Should deduplicate
        assert len(urls) == 2
        assert urls.count("https://example.com/page1") == 1

