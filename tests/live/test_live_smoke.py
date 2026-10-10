"""Read-only smoke tests with a real Rouvy account (never changes account data)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rouvy_api import RouvyClient

pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="module")]


class TestLiveReads:
    """Every read endpoint returns parseable data for a real account."""

    async def test_profile(self, live_client: RouvyClient) -> None:
        """The profile has an email and a unit system."""
        profile = await live_client.get_user_profile()

        assert profile.email is not None
        assert profile.units in {"METRIC", "IMPERIAL"}

    async def test_zones(self, live_client: RouvyClient) -> None:
        """Training zones include power and heart-rate boundaries."""
        zones = await live_client.get_training_zones()

        assert zones.power_zones or zones.power_zone_defaults
        assert zones.heart_rate_zones or zones.heart_rate_zone_defaults

    async def test_overview(self, live_client: RouvyClient) -> None:
        """The profile overview parses and includes career progress."""
        overview = await live_client.get_profile_overview()

        assert overview.career is not None

    async def test_secondary_reads(self, live_client: RouvyClient) -> None:
        """Every other read endpoint parses without errors."""
        now = datetime.now(UTC)

        await live_client.get_connected_apps()
        await live_client.get_weekly_activity_stats(now.year, now.month)
        await live_client.get_challenges()
        await live_client.get_routes()
        assert all(r.favorite for r in await live_client.get_favorite_routes())
        events = await live_client.get_events()
        assert all(e.event_id and e.starts_at for e in events)
        weeks = await live_client.get_weekly_activity_stats(now.year, now.month)
        assert all(w.week_start and w.week_end for w in weeks)
        await live_client.get_achievements()
        await live_client.get_trophies()
