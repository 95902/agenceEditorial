"""Robots.txt parser and caching (T101 - US5)."""

import re
import warnings
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

# Suppress SSL warnings for development
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import CrawlingError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class RobotsTxtParser:
    """Parser for robots.txt files."""

    def __init__(self, content: str, base_url: str) -> None:
        """Initialize parser with robots.txt content."""
        self.content = content
        self.base_url = base_url
        self.user_agents: dict[str, dict] = {}
        self.default_rules: dict = {}
        self._parse()

    def _parse(self) -> None:
        """Parse robots.txt content."""
        current_ua = None
        lines = self.content.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                current_ua = value
                if current_ua not in self.user_agents:
                    self.user_agents[current_ua] = {
                        "disallowed": [],
                        "allowed": [],
                        "crawl-delay": None,
                    }
            elif key == "disallow" and current_ua:
                if value:
                    self.user_agents[current_ua]["disallowed"].append(value)
            elif key == "allow" and current_ua:
                if value:
                    self.user_agents[current_ua]["allowed"].append(value)
            elif key == "crawl-delay" and current_ua:
                try:
                    self.user_agents[current_ua]["crawl-delay"] = int(float(value))
                except ValueError:
                    pass

        # Extract default rules (for * user-agent)
        if "*" in self.user_agents:
            self.default_rules = self.user_agents["*"]

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        """Check if URL is allowed for user agent."""
        rules = self.user_agents.get(user_agent, self.default_rules)
        if not rules:
            return True

        parsed_url = urlparse(url)
        path = parsed_url.path

        # Check disallowed paths
        for disallowed in rules.get("disallowed", []):
            if self._path_matches(path, disallowed):
                # Check if there's an allow rule that overrides
                allowed = False
                for allowed_path in rules.get("allowed", []):
                    if self._path_matches(path, allowed_path):
                        allowed = True
                        break
                if not allowed:
                    return False

        return True

    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern."""
        # Convert pattern to regex
        pattern = pattern.replace("*", ".*")
        pattern = pattern.replace("$", "\\$")
        return bool(re.match(pattern, path))

    def get_crawl_delay(self, user_agent: str = "*") -> Optional[int]:
        """Get crawl delay for user agent."""
        rules = self.user_agents.get(user_agent, self.default_rules)
        return rules.get("crawl-delay") if rules else None

    def get_disallowed_paths(self, user_agent: str = "*") -> List[str]:
        """Get disallowed paths for user agent."""
        rules = self.user_agents.get(user_agent, self.default_rules)
        return rules.get("disallowed", []) if rules else []


async def fetch_robots_txt(domain: str) -> Optional[str]:
    """Fetch robots.txt for a domain."""
    try:
        url = f"https://{domain}/robots.txt"
        # Disable SSL verification for development (can be configured via settings)
        async with httpx.AsyncClient(
            timeout=10.0,
            verify=False,  # Disable SSL verification for development
        ) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
            return None
    except Exception as e:
        logger.warning("Failed to fetch robots.txt", domain=domain, error=str(e))
        return None


async def parse_robots_txt(
    domain: str,
    db_session: Optional[AsyncSession] = None,
    use_cache: bool = True,
) -> Optional[RobotsTxtParser]:
    """
    Fetch and parse robots.txt for a domain with caching (T101 - US5).
    
    Args:
        domain: Domain name
        db_session: Database session for caching (optional)
        use_cache: Whether to use cache (default: True)
        
    Returns:
        RobotsTxtParser instance or None
    """
    # Check cache if enabled and db_session provided
    if use_cache and db_session:
        from python_scripts.database.crud_permissions import get_scraping_permission
        
        cached = await get_scraping_permission(db_session, domain)
        if cached:
            logger.debug("Using cached robots.txt", domain=domain)
            # Reconstruct parser from cached data
            if cached.robots_txt_content:
                parser = RobotsTxtParser(cached.robots_txt_content, f"https://{domain}")
                return parser
    
    # Fetch fresh robots.txt
    content = await fetch_robots_txt(domain)
    if not content:
        return None
    
    parser = RobotsTxtParser(content, f"https://{domain}")
    
    # Save to cache if db_session provided
    if db_session:
        from python_scripts.database.crud_permissions import create_or_update_scraping_permission
        
        # Extract disallowed paths
        disallowed_paths = parser.get_disallowed_paths()
        crawl_delay = parser.get_crawl_delay()
        
        # Determine if scraping is generally allowed
        # Check a few common paths
        test_paths = ["/", "/blog/", "/articles/"]
        scraping_allowed = any(parser.is_allowed(f"https://{domain}{path}") for path in test_paths)
        
        await create_or_update_scraping_permission(
            db_session,
            domain=domain,
            scraping_allowed=scraping_allowed,
            disallowed_paths=disallowed_paths,
            crawl_delay=crawl_delay,
            robots_txt_content=content,
        )
        logger.info("Robots.txt cached", domain=domain)
    
    return parser

