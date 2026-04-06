"""Tests for the Rouvy Home Assistant integration.

Uses pytest-homeassistant-custom-component for real HA test fixtures.
Tests config flow, coordinator, sensor setup, and service calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.api_client.errors import AuthenticationError, RouvyApiError
from custom_components.rouvy.api_client.models import (
    ActivitySummary,
    CareerStats,
    FriendsSummary,
    TrainingZones,
    UserProfile,
)
from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "secret123"
MOCK_CONFIG = {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD}

# Patch target: lazy imports in __init__.py resolve from the api module
_PATCH_CLIENT = "custom_components.rouvy.api.RouvyAsyncApiClient"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _make_profile(**overrides: object) -> UserProfile:
    """Create a UserProfile with sensible defaults."""
    defaults = {
        "email": MOCK_EMAIL,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "weight_kg": 80.0,
        "height_cm": 175.0,
        "units": "METRIC",
        "ftp_watts": 200,
        "ftp_source": "MANUAL",
        "max_heart_rate": 185,
        "gender": "MALE",
    }
    defaults.update(overrides)
    return UserProfile(**defaults)  # type: ignore[arg-type]


def _mock_entry() -> MockConfigEntry:
    """Create a mock config entry for the Rouvy integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_EMAIL,
        title=MOCK_EMAIL,
    )


def _mock_client(profile: UserProfile | None = None) -> AsyncMock:
    """Create a mock RouvyAsyncApiClient."""
    client = AsyncMock()
    client.async_validate_credentials = AsyncMock(return_value=True)
    client.async_get_user_profile = AsyncMock(return_value=profile or _make_profile())
    client.async_get_activity_stats = AsyncMock(return_value=[])
    client.async_get_challenges = AsyncMock(return_value=[])
    client.async_get_training_zones = AsyncMock(return_value=TrainingZones())
    client.async_get_connected_apps = AsyncMock(return_value=[])
    client.async_get_activity_summary = AsyncMock(return_value=ActivitySummary())
    client.async_get_favorite_routes = AsyncMock(return_value=[])
    client.async_get_friends = AsyncMock(return_value=FriendsSummary())
    client.async_update_user_settings = AsyncMock()
    client.async_update_user_profile = AsyncMock()
    client.async_update_user_social = AsyncMock()
    client.async_get_events = AsyncMock(return_value=[])
    client.async_register_event = AsyncMock(return_value=True)
    client.async_unregister_event = AsyncMock(return_value=True)
    client.async_register_challenge = AsyncMock(return_value=True)
    client.async_get_career = AsyncMock(return_value=CareerStats())
    client.async_update_timezone = AsyncMock()
    client.async_update_ftp = AsyncMock()
    client.async_update_zones = AsyncMock()
    return client


# ===================================================================
# Config flow tests
# ===================================================================


class TestConfigFlow:
    """Test the Rouvy config flow."""

    async def test_user_step_shows_form(self, hass: HomeAssistant) -> None:
        """Test that the user step shows the email/password form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    async def test_user_step_creates_entry_on_valid_credentials(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test successful credential validation creates a config entry."""
        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                return_value=True,
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=MOCK_CONFIG
            )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == MOCK_EMAIL
        assert result["data"] == MOCK_CONFIG

    async def test_user_step_invalid_auth(self, hass: HomeAssistant) -> None:
        """Test that invalid credentials show an auth error."""
        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                return_value=False,
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=MOCK_CONFIG
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_user_step_connection_error(self, hass: HomeAssistant) -> None:
        """Test that a connection error shows the cannot_connect error."""
        import aiohttp

        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                side_effect=aiohttp.ClientError("timeout"),
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=MOCK_CONFIG
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_step_unexpected_error(self, hass: HomeAssistant) -> None:
        """Test that an unexpected error shows the unknown error."""
        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                side_effect=RuntimeError("something broke"),
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=MOCK_CONFIG
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_user_step_duplicate_entry_aborts(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that a duplicate config entry aborts."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                return_value=True,
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=MOCK_CONFIG
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"

    async def test_reauth_shows_form(self, hass: HomeAssistant) -> None:
        """Test that the reauth step shows the credentials form."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

    async def test_reauth_success(self, hass: HomeAssistant) -> None:
        """Test successful reauth updates the entry and reloads."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        result = await entry.start_reauth_flow(hass)

        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                return_value=True,
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_EMAIL: "new@example.com", CONF_PASSWORD: "newpass"},
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    async def test_reauth_invalid_credentials(self, hass: HomeAssistant) -> None:
        """Test reauth with invalid credentials shows error."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        result = await entry.start_reauth_flow(hass)

        with patch(
            "custom_components.rouvy.config_flow.RouvyAsyncApiClient",
        ) as mock_cls:
            mock_cls.return_value.async_validate_credentials = AsyncMock(
                return_value=False,
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=MOCK_CONFIG,
            )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


# ===================================================================
# Integration setup tests
# ===================================================================


class TestSetupEntry:
    """Test async_setup_entry and async_unload_entry."""

    async def test_setup_entry_success(self, hass: HomeAssistant) -> None:
        """Test successful integration setup."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        with patch(_PATCH_CLIENT, return_value=_mock_client()):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

    async def test_setup_entry_auth_failure(self, hass: HomeAssistant) -> None:
        """Test that a single auth failure during first refresh retries (not permanent)."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        client = _mock_client()
        client.async_get_user_profile = AsyncMock(
            side_effect=AuthenticationError("bad creds"),
        )

        with patch(_PATCH_CLIENT, return_value=client):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # Single auth failure triggers retry (not permanent auth error)
        assert entry.state is ConfigEntryState.SETUP_RETRY

    async def test_setup_entry_api_failure(self, hass: HomeAssistant) -> None:
        """Test that API error during first refresh sets up retry."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        client = _mock_client()
        client.async_get_user_profile = AsyncMock(
            side_effect=RouvyApiError("server error"),
        )

        with patch(_PATCH_CLIENT, return_value=client):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY

    async def test_unload_entry(self, hass: HomeAssistant) -> None:
        """Test successful integration unload."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        with patch(_PATCH_CLIENT, return_value=_mock_client()):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


# ===================================================================
# Sensor tests
# ===================================================================


class TestSensors:
    """Test Rouvy sensor entities."""

    async def _setup(
        self, hass: HomeAssistant, profile: UserProfile | None = None
    ) -> MockConfigEntry:
        """Set up the integration with a mock client."""
        entry = _mock_entry()
        entry.add_to_hass(hass)

        with patch(_PATCH_CLIENT, return_value=_mock_client(profile)):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return entry

    async def test_weight_sensor(self, hass: HomeAssistant) -> None:
        """Test weight sensor reports correct value."""
        await self._setup(hass, _make_profile(weight_kg=85.5))
        state = hass.states.get("sensor.rouvy_weight")
        assert state is not None
        assert float(state.state) == 85.5

    async def test_height_sensor(self, hass: HomeAssistant) -> None:
        """Test height sensor reports correct value."""
        await self._setup(hass, _make_profile(height_cm=180.0))
        state = hass.states.get("sensor.rouvy_height")
        assert state is not None
        assert float(state.state) == 180.0

    async def test_ftp_sensor(self, hass: HomeAssistant) -> None:
        """Test FTP sensor reports correct value."""
        await self._setup(hass, _make_profile(ftp_watts=250))
        state = hass.states.get("sensor.rouvy_ftp")
        assert state is not None
        assert int(state.state) == 250

    async def test_max_heart_rate_sensor(self, hass: HomeAssistant) -> None:
        """Test max HR sensor reports correct value."""
        await self._setup(hass, _make_profile(max_heart_rate=195))
        state = hass.states.get("sensor.rouvy_max_heart_rate")
        assert state is not None
        assert int(state.state) == 195

    async def test_units_sensor(self, hass: HomeAssistant) -> None:
        """Test units sensor reports correct value."""
        await self._setup(hass, _make_profile(units="IMPERIAL"))
        state = hass.states.get("sensor.rouvy_units")
        assert state is not None
        assert state.state == "IMPERIAL"

    async def test_name_sensor(self, hass: HomeAssistant) -> None:
        """Test name sensor reports full name."""
        await self._setup(hass, _make_profile(first_name="John", last_name="Doe"))
        state = hass.states.get("sensor.rouvy_name")
        assert state is not None
        assert state.state == "John Doe"

    async def test_name_sensor_fallback_to_username(self, hass: HomeAssistant) -> None:
        """Test name sensor falls back to username when names are empty."""
        await self._setup(hass, _make_profile(first_name="", last_name="", username="jdoe"))
        state = hass.states.get("sensor.rouvy_name")
        assert state is not None
        assert state.state == "jdoe"

    async def test_zero_weight_shows_unknown(self, hass: HomeAssistant) -> None:
        """Test that zero weight returns unknown state."""
        await self._setup(hass, _make_profile(weight_kg=0.0))
        state = hass.states.get("sensor.rouvy_weight")
        assert state is not None
        assert state.state == "unknown"

    async def test_all_sensors_created(self, hass: HomeAssistant) -> None:
        """Test that all 33 sensor entities are created.

        6 profile + 6 weekly + 2 challenges + 2 zones
        + 2 connected apps + 5 activity + 2 routes + 2 events + 4 career + 2 friends.
        """
        await self._setup(hass)
        sensor_states = [
            s for s in hass.states.async_all() if s.entity_id.startswith("sensor.rouvy")
        ]
        assert len(sensor_states) == 41, (
            f"Expected 41 sensors, got {len(sensor_states)}: {[s.entity_id for s in sensor_states]}"
        )


# ===================================================================
# Service tests
# ===================================================================


class TestServices:
    """Test Rouvy service calls."""

    async def _setup(self, hass: HomeAssistant) -> AsyncMock:
        """Set up the integration and return the mock client."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        client = _mock_client()

        with patch(_PATCH_CLIENT, return_value=client):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return client

    async def test_update_weight_service(self, hass: HomeAssistant) -> None:
        """Test update_weight service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(DOMAIN, "update_weight", {"weight": 82.5}, blocking=True)
        client.async_update_user_settings.assert_called_once_with({"weight": 82.5})

    async def test_update_height_service(self, hass: HomeAssistant) -> None:
        """Test update_height service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(DOMAIN, "update_height", {"height": 180}, blocking=True)
        client.async_update_user_settings.assert_called_once_with({"height": 180})

    async def test_update_settings_service(self, hass: HomeAssistant) -> None:
        """Test update_settings service calls the API with arbitrary data."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN,
            "update_settings",
            {"settings": {"weight": 75, "units": "IMPERIAL"}},
            blocking=True,
        )
        client.async_update_user_settings.assert_called_once_with(
            {"weight": 75, "units": "IMPERIAL"}
        )

    async def test_register_challenge_service(self, hass: HomeAssistant) -> None:
        """Test register_challenge service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN, "register_challenge", {"slug": "april-2026"}, blocking=True
        )
        client.async_register_challenge.assert_called_once_with("april-2026")

    async def test_register_event_service(self, hass: HomeAssistant) -> None:
        """Test register_event service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN, "register_event", {"event_id": "abc-123"}, blocking=True
        )
        client.async_register_event.assert_called_once_with("abc-123")

    async def test_unregister_event_service(self, hass: HomeAssistant) -> None:
        """Test unregister_event service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN, "unregister_event", {"event_id": "abc-123"}, blocking=True
        )
        client.async_unregister_event.assert_called_once_with("abc-123")

    async def test_update_profile_service(self, hass: HomeAssistant) -> None:
        """Test update_profile service calls the API with profile fields."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN,
            "update_profile",
            {"userName": "NewName", "accountPrivacy": "PRIVATE"},
            blocking=True,
        )
        client.async_update_user_social.assert_called_once_with("PRIVATE")
        client.async_update_user_profile.assert_called_once_with({"userName": "NewName"})

    async def test_update_units_service(self, hass: HomeAssistant) -> None:
        """Test update_units service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(DOMAIN, "update_units", {"units": "IMPERIAL"}, blocking=True)
        client.async_update_user_settings.assert_called_once_with({"units": "IMPERIAL"})

    async def test_update_timezone_service(self, hass: HomeAssistant) -> None:
        """Test update_timezone service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN, "update_timezone", {"timezone": "America/New_York"}, blocking=True
        )
        client.async_update_timezone.assert_called_once_with("America/New_York")

    async def test_update_ftp_service(self, hass: HomeAssistant) -> None:
        """Test update_ftp service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN,
            "update_ftp",
            {"ftp_source": "MANUAL", "value": 250},
            blocking=True,
        )
        client.async_update_ftp.assert_called_once_with("MANUAL", 250)

    async def test_update_zones_service(self, hass: HomeAssistant) -> None:
        """Test update_zones service calls the API."""
        client = await self._setup(hass)
        await hass.services.async_call(
            DOMAIN,
            "update_zones",
            {"zone_type": "power", "zones": [55, 75, 90, 105, 120, 150]},
            blocking=True,
        )
        client.async_update_zones.assert_called_once_with("power", [55, 75, 90, 105, 120, 150])

    async def test_get_profile_service(self, hass: HomeAssistant) -> None:
        """Test get_profile service returns profile data."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_profile", {}, blocking=True, return_response=True
        )
        assert "profile" in result
        assert result["profile"]["email"] == "test@example.com"

    async def test_get_events_service(self, hass: HomeAssistant) -> None:
        """Test get_events service returns events list."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_events", {}, blocking=True, return_response=True
        )
        assert "events" in result
        assert isinstance(result["events"], list)

    async def test_get_challenges_service(self, hass: HomeAssistant) -> None:
        """Test get_challenges service returns challenges list."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_challenges", {}, blocking=True, return_response=True
        )
        assert "challenges" in result
        assert isinstance(result["challenges"], list)

    async def test_get_routes_service(self, hass: HomeAssistant) -> None:
        """Test get_routes service returns routes list."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_routes", {}, blocking=True, return_response=True
        )
        assert "routes" in result
        assert isinstance(result["routes"], list)

    async def test_get_activities_service(self, hass: HomeAssistant) -> None:
        """Test get_activities service returns activities list."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_activities", {}, blocking=True, return_response=True
        )
        assert "activities" in result
        assert isinstance(result["activities"], list)

    async def test_get_career_service(self, hass: HomeAssistant) -> None:
        """Test get_career service returns career data."""
        await self._setup(hass)
        result = await hass.services.async_call(
            DOMAIN, "get_career", {}, blocking=True, return_response=True
        )
        assert "career" in result
        assert "level" in result["career"]
