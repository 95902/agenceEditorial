"""Unit tests for robots.txt parser."""

import pytest

from python_scripts.ingestion.robots_txt import RobotsTxtParser, fetch_robots_txt, parse_robots_txt


@pytest.mark.unit
class TestRobotsTxtParser:
    """Test RobotsTxtParser class."""

    def test_parse_simple_robots_txt(self) -> None:
        """Test parsing simple robots.txt."""
        content = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/
Crawl-delay: 2
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert "*" in parser.user_agents
        assert "/admin/" in parser.user_agents["*"]["disallowed"]
        assert "/private/" in parser.user_agents["*"]["disallowed"]
        assert "/public/" in parser.user_agents["*"]["allowed"]
        assert parser.user_agents["*"]["crawl-delay"] == 2

    def test_parse_multiple_user_agents(self) -> None:
        """Test parsing robots.txt with multiple user agents."""
        content = """
User-agent: Googlebot
Disallow: /private/
Crawl-delay: 1

User-agent: *
Disallow: /admin/
Crawl-delay: 2
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert "Googlebot" in parser.user_agents
        assert "*" in parser.user_agents
        assert parser.user_agents["Googlebot"]["crawl-delay"] == 1
        assert parser.user_agents["*"]["crawl-delay"] == 2

    def test_is_allowed_simple_path(self) -> None:
        """Test is_allowed with simple paths."""
        content = """
User-agent: *
Disallow: /admin/
Allow: /admin/public/
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert parser.is_allowed("https://example.com/home") is True
        assert parser.is_allowed("https://example.com/admin/") is False
        assert parser.is_allowed("https://example.com/admin/public/") is True

    def test_is_allowed_wildcard_patterns(self) -> None:
        """Test is_allowed with wildcard patterns."""
        content = """
User-agent: *
Disallow: /private/*
Allow: /private/public/
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert parser.is_allowed("https://example.com/private/secret") is False
        assert parser.is_allowed("https://example.com/private/public/") is True

    def test_get_crawl_delay(self) -> None:
        """Test get_crawl_delay."""
        content = """
User-agent: *
Crawl-delay: 5

User-agent: Googlebot
Crawl-delay: 1
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert parser.get_crawl_delay() == 5
        assert parser.get_crawl_delay("Googlebot") == 1
        assert parser.get_crawl_delay("UnknownBot") == 5  # Falls back to *

    def test_get_crawl_delay_none(self) -> None:
        """Test get_crawl_delay when not specified."""
        content = """
User-agent: *
Disallow: /admin/
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert parser.get_crawl_delay() is None

    def test_get_disallowed_paths(self) -> None:
        """Test get_disallowed_paths."""
        content = """
User-agent: *
Disallow: /admin/
Disallow: /private/
"""
        parser = RobotsTxtParser(content, "https://example.com")
        disallowed = parser.get_disallowed_paths()
        assert "/admin/" in disallowed
        assert "/private/" in disallowed

    def test_parse_empty_robots_txt(self) -> None:
        """Test parsing empty robots.txt."""
        parser = RobotsTxtParser("", "https://example.com")
        assert parser.user_agents == {}
        assert parser.is_allowed("https://example.com/any/path") is True

    def test_parse_comments(self) -> None:
        """Test parsing robots.txt with comments."""
        content = """
# This is a comment
User-agent: *
# Another comment
Disallow: /admin/
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert "/admin/" in parser.user_agents["*"]["disallowed"]

    def test_crawl_delay_float_conversion(self) -> None:
        """Test crawl-delay with float value."""
        content = """
User-agent: *
Crawl-delay: 2.5
"""
        parser = RobotsTxtParser(content, "https://example.com")
        assert parser.get_crawl_delay() == 2  # Should convert to int

    def test_path_matches_end_anchor(self) -> None:
        """Test path matching with $ end anchor."""
        content = """
User-agent: *
Disallow: /admin$
"""
        parser = RobotsTxtParser(content, "https://example.com")
        # Note: This is a simplified test - actual regex matching may vary
        assert parser.is_allowed("https://example.com/admin") is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchRobotsTxt:
    """Test fetch_robots_txt function."""

    async def test_fetch_robots_txt_success(self, mocker) -> None:
        """Test successful fetch of robots.txt."""
        # Mock httpx response
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /admin/"

        mock_client = mocker.AsyncMock()
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        content = await fetch_robots_txt("example.com")
        assert content is not None
        assert "User-agent" in content

    async def test_fetch_robots_txt_not_found(self, mocker) -> None:
        """Test fetch when robots.txt not found."""
        mock_response = mocker.Mock()
        mock_response.status_code = 404

        mock_client = mocker.AsyncMock()
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        content = await fetch_robots_txt("example.com")
        assert content is None

    async def test_fetch_robots_txt_network_error(self, mocker) -> None:
        """Test fetch when network error occurs."""
        mock_client = mocker.AsyncMock()
        mock_client.get = mocker.AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        content = await fetch_robots_txt("example.com")
        assert content is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestParseRobotsTxt:
    """Test parse_robots_txt function."""

    async def test_parse_robots_txt_success(self, mocker) -> None:
        """Test successful parse of robots.txt."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /admin/\nCrawl-delay: 2"

        mock_client = mocker.AsyncMock()
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        parser = await parse_robots_txt("example.com")
        assert parser is not None
        assert parser.get_crawl_delay() == 2
        assert "/admin/" in parser.get_disallowed_paths()

    async def test_parse_robots_txt_not_found(self, mocker) -> None:
        """Test parse when robots.txt not found."""
        mock_response = mocker.Mock()
        mock_response.status_code = 404

        mock_client = mocker.AsyncMock()
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        parser = await parse_robots_txt("example.com")
        assert parser is None

