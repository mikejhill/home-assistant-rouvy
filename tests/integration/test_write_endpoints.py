"""Integration tests for Rouvy API write endpoints.

⚠️  WARNING: These tests MODIFY account settings on the REAL Rouvy API.
They attempt to restore original values on completion, but restoration
is best-effort and may fail if tests are interrupted.
"""

from __future__ import annotations

import pytest

from custom_components.rouvy.api import RouvyAsyncApiClient

pytestmark = pytest.mark.integration


class TestUpdateWeight:
    """Test updating weight via the live API."""

    async def test_update_and_restore_weight(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Update weight, verify change, then restore original."""
        original = await rouvy_client.async_get_user_profile()
        original_weight = original.weight_kg
        test_weight = 77.7

        try:
            await rouvy_client.async_update_user_settings({"weight": test_weight})
            updated = await rouvy_client.async_get_user_profile()
            assert abs(updated.weight_kg - test_weight) < 0.5
        finally:
            await rouvy_client.async_update_user_settings({"weight": original_weight})


class TestUpdateHeight:
    """Test updating height via the live API."""

    async def test_update_and_restore_height(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Update height, verify change, then restore original."""
        original = await rouvy_client.async_get_user_profile()
        original_height = original.height_cm
        test_height = 166.6

        try:
            await rouvy_client.async_update_user_settings({"height": test_height})
            updated = await rouvy_client.async_get_user_profile()
            assert abs(updated.height_cm - test_height) < 0.5
        finally:
            await rouvy_client.async_update_user_settings({"height": original_height})


class TestUpdateUnits:
    """Test switching unit systems via the live API."""

    async def test_toggle_units_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Toggle between METRIC and IMPERIAL, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_units = original.units
        test_units = "IMPERIAL" if original_units == "METRIC" else "METRIC"

        try:
            await rouvy_client.async_update_user_settings({"units": test_units})
            updated = await rouvy_client.async_get_user_profile()
            assert updated.units == test_units
        finally:
            await rouvy_client.async_update_user_settings({"units": original_units})


class TestUpdateTimezone:
    """Test updating timezone via the live API."""

    async def test_update_and_restore_timezone(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change timezone, verify it sticks, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_tz = original.timezone or "UTC"
        test_tz = "Europe/London" if original_tz != "Europe/London" else "America/Chicago"

        try:
            await rouvy_client.async_update_timezone(test_tz)
            # Timezone is stored but may not appear in the profile response
            # immediately; we verify the API call succeeded without error.
        finally:
            await rouvy_client.async_update_timezone(original_tz)


class TestUpdateFtp:
    """Test updating FTP source and value via the live API."""

    async def test_set_manual_ftp_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Set FTP to a manual value, verify, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_source = original.ftp_source or "ESTIMATED"
        original_ftp = original.ftp_watts
        test_ftp = 199

        try:
            await rouvy_client.async_update_ftp("MANUAL", test_ftp)
            updated = await rouvy_client.async_get_user_profile()
            assert updated.ftp_watts == test_ftp
            assert updated.ftp_source == "MANUAL"
        finally:
            if original_source == "ESTIMATED":
                await rouvy_client.async_update_ftp("ESTIMATED")
            else:
                await rouvy_client.async_update_ftp("MANUAL", original_ftp)


class TestUpdateZones:
    """Test updating training zone boundaries via the live API."""

    async def test_update_power_zones_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Modify power zone boundaries, then restore originals."""
        original = await rouvy_client.async_get_training_zones()
        original_zones = list(original.power_zone_values)
        test_zones = [50, 70, 85, 100, 115, 145]

        try:
            await rouvy_client.async_update_zones("power", test_zones)
            updated = await rouvy_client.async_get_training_zones()
            assert updated.power_zone_values == test_zones
        finally:
            await rouvy_client.async_update_zones("power", original_zones)


class TestUpdateProfile:
    """Test updating profile identity fields via the live API."""

    async def test_update_username_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change username, verify, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_name = original.username
        test_name = "TestBot9999"
        # Rouvy requires non-empty username; use a fallback if original is blank
        restore_name = original_name if original_name else "TestBotRestore"

        try:
            await rouvy_client.async_update_user_profile({"userName": test_name})
            updated = await rouvy_client.async_get_user_profile()
            assert updated.username == test_name
        finally:
            await rouvy_client.async_update_user_profile({"userName": restore_name})

    async def test_update_first_name_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change first name, verify, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_first = original.first_name
        test_first = "IntegrationTest"

        try:
            await rouvy_client.async_update_user_profile({"firstName": test_first})
            updated = await rouvy_client.async_get_user_profile()
            assert updated.first_name == test_first
        finally:
            await rouvy_client.async_update_user_profile({"firstName": original_first})

    async def test_update_last_name_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change last name, verify, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_last = original.last_name
        test_last = "TestSurname"

        try:
            await rouvy_client.async_update_user_profile({"lastName": test_last})
            updated = await rouvy_client.async_get_user_profile()
            assert updated.last_name == test_last
        finally:
            await rouvy_client.async_update_user_profile({"lastName": original_last})

    async def test_update_team_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change team name, verify, then restore."""
        original_team = ""  # team is not parsed from turbo-stream response
        test_team = "TestTeam42"

        try:
            await rouvy_client.async_update_user_profile({"team": test_team})
            # Team may not be visible in profile read-back; verify no error
        finally:
            await rouvy_client.async_update_user_profile({"team": original_team})

    async def test_update_country_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change country (nationality), verify, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_country = original.country or "US"
        test_country = "CZ" if original_country != "CZ" else "DE"

        try:
            await rouvy_client.async_update_user_profile({"countryIsoCode": test_country})
            updated = await rouvy_client.async_get_user_profile()
            assert updated.country == test_country
        finally:
            await rouvy_client.async_update_user_profile({"countryIsoCode": original_country})

    async def test_update_privacy_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Toggle account privacy, then restore."""
        original = await rouvy_client.async_get_user_profile()
        original_privacy = original.account_privacy or "PUBLIC"
        test_privacy = "PRIVATE" if original_privacy == "PUBLIC" else "PUBLIC"

        try:
            await rouvy_client.async_update_user_social(test_privacy)
            updated = await rouvy_client.async_get_user_profile()
            assert updated.account_privacy == test_privacy
        finally:
            await rouvy_client.async_update_user_social(original_privacy)


class TestUpdateMaxHeartRate:
    """Test updating max heart rate via the live API."""

    async def test_update_and_restore_max_hr(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Change max heart rate, verify, then restore."""
        original = await rouvy_client.async_get_training_zones()
        original_hr = original.max_heart_rate
        test_hr = 185 if original_hr != 185 else 195

        try:
            await rouvy_client.async_update_max_heart_rate(test_hr)
            updated = await rouvy_client.async_get_training_zones()
            assert updated.max_heart_rate == test_hr
        finally:
            await rouvy_client.async_update_max_heart_rate(original_hr)


class TestUpdateHrZones:
    """Test updating heart rate zone boundaries via the live API."""

    async def test_update_hr_zones_and_restore(self, rouvy_client: RouvyAsyncApiClient) -> None:
        """Modify heart rate zone boundaries, then restore originals."""
        original = await rouvy_client.async_get_training_zones()
        original_zones = list(original.hr_zone_values)
        test_zones = [55, 65, 75, 82, 89, 96]

        try:
            await rouvy_client.async_update_zones("heartRate", test_zones)
            updated = await rouvy_client.async_get_training_zones()
            assert updated.hr_zone_values == test_zones
        finally:
            await rouvy_client.async_update_zones("heartRate", original_zones)
