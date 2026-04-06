"""Integration tests for Rouvy API read endpoints.

⚠️  WARNING: These tests run against the REAL Rouvy API.
"""

from __future__ import annotations

import pytest

from custom_components.rouvy.api import RouvyAsyncApiClient
from custom_components.rouvy.api_client.models import (
    ActivitySummary,
    CareerStats,
    FriendsSummary,
    TrainingZones,
    UserProfile,
)

pytestmark = pytest.mark.integration


class TestReadProfile:
    """Test reading the user profile from the live API."""

    async def test_get_user_profile(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Profile should return a populated UserProfile."""
        profile = await rouvy_client.async_get_user_profile()
        assert isinstance(profile, UserProfile)
        assert profile.email != ""
        assert isinstance(profile.weight_kg, float)
        assert isinstance(profile.height_cm, float)

    async def test_profile_has_ftp(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Profile should include FTP data."""
        profile = await rouvy_client.async_get_user_profile()
        assert profile.ftp_watts >= 0
        assert profile.ftp_source in ("MANUAL", "ESTIMATED", "")

    async def test_profile_units_and_timezone(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Profile should include valid units and timezone."""
        profile = await rouvy_client.async_get_user_profile()
        assert profile.units in ("METRIC", "IMPERIAL")
        if profile.timezone is not None:
            assert isinstance(profile.timezone, str)
            assert len(profile.timezone) > 0

    async def test_profile_max_heart_rate(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Profile should include max heart rate if set."""
        profile = await rouvy_client.async_get_user_profile()
        if profile.max_heart_rate is not None:
            assert isinstance(profile.max_heart_rate, int)
            assert 50 <= profile.max_heart_rate <= 250


class TestReadTrainingZones:
    """Test reading training zones from the live API."""

    async def test_get_training_zones(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Zones should return power and HR zone data (custom or default)."""
        zones = await rouvy_client.async_get_training_zones()
        assert isinstance(zones, TrainingZones)
        assert len(zones.power_zone_values) > 0 or len(zones.power_zone_defaults) > 0
        assert len(zones.hr_zone_values) > 0 or len(zones.hr_zone_defaults) > 0

    async def test_zones_have_ftp_and_max_hr(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Zones should include FTP watts and max heart rate reference values."""
        zones = await rouvy_client.async_get_training_zones()
        assert zones.ftp_watts >= 0
        assert zones.max_heart_rate >= 0


class TestReadConnectedApps:
    """Test reading connected apps from the live API."""

    async def test_get_connected_apps(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return a list of ConnectedApp objects."""
        apps = await rouvy_client.async_get_connected_apps()
        assert isinstance(apps, list)


class TestReadActivitySummary:
    """Test reading activity summary from the live API."""

    async def test_get_activity_summary(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return an ActivitySummary."""
        summary = await rouvy_client.async_get_activity_summary()
        assert isinstance(summary, ActivitySummary)
        assert isinstance(summary.recent_activities, list)


class TestReadActivityStats:
    """Test reading activity stats from the live API."""

    async def test_get_activity_stats(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return weekly stats for the current month."""
        from datetime import datetime

        now = datetime.now()
        stats = await rouvy_client.async_get_activity_stats(now.year, now.month)
        assert isinstance(stats, list)


class TestReadChallenges:
    """Test reading challenges from the live API."""

    async def test_get_challenges(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return a list of challenges."""
        challenges = await rouvy_client.async_get_challenges()
        assert isinstance(challenges, list)


class TestReadEvents:
    """Test reading events from the live API."""

    async def test_get_events(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return a list of events."""
        events = await rouvy_client.async_get_events()
        assert isinstance(events, list)


class TestReadRoutes:
    """Test reading favorite routes from the live API."""

    async def test_get_favorite_routes(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return a list of routes."""
        routes = await rouvy_client.async_get_favorite_routes()
        assert isinstance(routes, list)


class TestReadCareer:
    """Test reading career stats from the live API."""

    async def test_get_career(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return career stats with a level."""
        career = await rouvy_client.async_get_career()
        assert isinstance(career, CareerStats)
        assert career.level >= 0


class TestReadFriends:
    """Test reading friends from the live API."""

    async def test_get_friends(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Should return a friends summary."""
        friends = await rouvy_client.async_get_friends()
        assert isinstance(friends, FriendsSummary)
        assert friends.total_friends >= 0
