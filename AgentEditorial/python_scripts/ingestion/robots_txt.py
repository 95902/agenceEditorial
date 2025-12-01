"""Robots.txt parser and caching."""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx

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
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
            return None
    except Exception as e:
        logger.warning("Failed to fetch robots.txt", domain=domain, error=str(e))
        return None


async def parse_robots_txt(domain: str) -> Optional[RobotsTxtParser]:
    """Fetch and parse robots.txt for a domain."""
    content = await fetch_robots_txt(domain)
    if content:
        return RobotsTxtParser(content, f"https://{domain}")
    return None

