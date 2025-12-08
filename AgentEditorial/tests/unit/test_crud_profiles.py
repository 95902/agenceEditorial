"""Unit tests for site profile CRUD operations."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.crud_profiles import (
    create_site_profile,
    get_site_history,
    get_site_profile_by_domain,
    list_site_profiles,
)
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import SiteProfile


@pytest.mark.unit
@pytest.mark.asyncio
class TestSiteProfileCRUD:
    """Test CRUD operations for SiteProfile."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        """Create database session for tests."""
        async with AsyncSessionLocal() as session:
            yield session
            await session.rollback()

    async def test_create_site_profile(self, db_session: AsyncSession) -> None:
        """Test creating a site profile."""
        profile = await create_site_profile(
            db_session,
            domain="example.com",
            language_level="intermediate",
            editorial_tone="professional",
            pages_analyzed=10,
        )
        assert profile.domain == "example.com"
        assert profile.language_level == "intermediate"
        assert profile.editorial_tone == "professional"
        assert profile.pages_analyzed == 10
        assert profile.id is not None

    async def test_get_site_profile_by_domain(self, db_session: AsyncSession) -> None:
        """Test getting site profile by domain."""
        # Create a profile
        await create_site_profile(
            db_session,
            domain="test.com",
            language_level="advanced",
        )

        # Retrieve it
        profile = await get_site_profile_by_domain(db_session, "test.com")
        assert profile is not None
        assert profile.domain == "test.com"
        assert profile.language_level == "advanced"

    async def test_get_site_profile_not_found(self, db_session: AsyncSession) -> None:
        """Test getting non-existent site profile."""
        profile = await get_site_profile_by_domain(db_session, "nonexistent.com")
        assert profile is None

    async def test_list_site_profiles(self, db_session: AsyncSession) -> None:
        """Test listing site profiles."""
        # Create multiple profiles
        await create_site_profile(db_session, domain="site1.com")
        await create_site_profile(db_session, domain="site2.com")
        await create_site_profile(db_session, domain="site3.com")

        # List them
        profiles = await list_site_profiles(db_session, limit=10)
        assert len(profiles) >= 3
        domains = [p.domain for p in profiles]
        assert "site1.com" in domains
        assert "site2.com" in domains
        assert "site3.com" in domains

    async def test_list_site_profiles_pagination(self, db_session: AsyncSession) -> None:
        """Test listing site profiles with pagination."""
        # Create multiple profiles
        for i in range(5):
            await create_site_profile(db_session, domain=f"site{i}.com")

        # Test limit
        profiles = await list_site_profiles(db_session, limit=2)
        assert len(profiles) == 2

        # Test offset
        profiles_offset = await list_site_profiles(db_session, limit=2, offset=2)
        assert len(profiles_offset) == 2
        # Should be different profiles
        assert profiles[0].domain != profiles_offset[0].domain


@pytest.mark.unit
@pytest.mark.asyncio
class TestSiteHistory:
    """Test site history queries (T066 - US2)."""

    async def test_get_site_history_single_entry(self, db_session: AsyncSession) -> None:
        """Test getting history for domain with single analysis."""
        domain = "example.com"
        await create_site_profile(
            db_session,
            domain=domain,
            language_level="intermediate",
            pages_analyzed=5,
        )

        history = await get_site_history(db_session, domain)
        assert len(history) == 1
        assert history[0].domain == domain
        assert history[0].language_level == "intermediate"
        assert history[0].pages_analyzed == 5

    async def test_get_site_history_multiple_entries(self, db_session: AsyncSession) -> None:
        """Test getting history for domain with multiple analyses."""
        domain = "example.com"
        base_time = datetime.now(timezone.utc)

        # Create multiple profiles with different dates
        for i in range(3):
            await create_site_profile(
                db_session,
                domain=domain,
                language_level=f"level{i}",
                pages_analyzed=10 + i,
                analysis_date=base_time.replace(day=1 + i),
            )

        history = await get_site_history(db_session, domain)
        assert len(history) == 3

        # Should be ordered by analysis_date descending (most recent first)
        assert history[0].analysis_date >= history[1].analysis_date
        assert history[1].analysis_date >= history[2].analysis_date

    async def test_get_site_history_limit(self, db_session: AsyncSession) -> None:
        """Test getting history with limit parameter."""
        domain = "example.com"
        base_time = datetime.now(timezone.utc)

        # Create 5 profiles
        for i in range(5):
            await create_site_profile(
                db_session,
                domain=domain,
                language_level=f"level{i}",
                analysis_date=base_time.replace(day=1 + i),
            )

        # Test with limit
        history = await get_site_history(db_session, domain, limit=3)
        assert len(history) == 3

        # Should return most recent 3
        assert history[0].analysis_date >= history[1].analysis_date
        assert history[1].analysis_date >= history[2].analysis_date

    async def test_get_site_history_empty(self, db_session: AsyncSession) -> None:
        """Test getting history for domain with no analyses."""
        history = await get_site_history(db_session, "nonexistent.com")
        assert len(history) == 0

    async def test_get_site_history_excludes_invalid(self, db_session: AsyncSession) -> None:
        """Test that invalid profiles are excluded from history."""
        domain = "example.com"
        base_time = datetime.now(timezone.utc)

        # Create valid profile
        valid_profile = await create_site_profile(
            db_session,
            domain=domain,
            language_level="valid",
            analysis_date=base_time,
        )

        # Create invalid profile
        invalid_profile = await create_site_profile(
            db_session,
            domain=domain,
            language_level="invalid",
            analysis_date=base_time.replace(day=2),
            is_valid=False,
        )

        history = await get_site_history(db_session, domain)
        assert len(history) == 1
        assert history[0].id == valid_profile.id
        assert history[0].is_valid is True

    async def test_get_site_history_different_domains(self, db_session: AsyncSession) -> None:
        """Test that history only returns profiles for specified domain."""
        base_time = datetime.now(timezone.utc)

        # Create profiles for different domains
        await create_site_profile(
            db_session,
            domain="domain1.com",
            language_level="level1",
            analysis_date=base_time,
        )
        await create_site_profile(
            db_session,
            domain="domain2.com",
            language_level="level2",
            analysis_date=base_time,
        )

        # Get history for domain1 only
        history1 = await get_site_history(db_session, "domain1.com")
        assert len(history1) == 1
        assert history1[0].domain == "domain1.com"

        # Get history for domain2 only
        history2 = await get_site_history(db_session, "domain2.com")
        assert len(history2) == 1
        assert history2[0].domain == "domain2.com"

    async def test_get_site_history_ordering(self, db_session: AsyncSession) -> None:
        """Test that history is ordered by analysis_date descending."""
        domain = "example.com"
        base_time = datetime.now(timezone.utc)

        # Create profiles in random order
        await create_site_profile(
            db_session,
            domain=domain,
            language_level="oldest",
            analysis_date=base_time.replace(day=1),
        )
        await create_site_profile(
            db_session,
            domain=domain,
            language_level="newest",
            analysis_date=base_time.replace(day=3),
        )
        await create_site_profile(
            db_session,
            domain=domain,
            language_level="middle",
            analysis_date=base_time.replace(day=2),
        )

        history = await get_site_history(db_session, domain)
        assert len(history) == 3

        # Verify descending order (newest first)
        assert history[0].language_level == "newest"
        assert history[1].language_level == "middle"
        assert history[2].language_level == "oldest"

