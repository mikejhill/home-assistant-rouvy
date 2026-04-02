"""Tests for the Home Assistant async API client.

Uses pytest-asyncio and unittest.mock to test RouvyAsyncApiClient
without requiring a live Home Assistant instance or network access.
"""

import json
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from rouvy_api_client.errors import AuthenticationError, RouvyApiError
from rouvy_api_client.models import UserProfile

# Mock homeassistant modules so custom_components.rouvy can be imported
# without an actual HA installation.
_HA_MODULES = [
    "homeassistant", "homeassistant.const", "homeassistant.core",
    "homeassistant.config_entries", "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.components", "homeassistant.components.sensor",
    "homeassistant.exceptions", "homeassistant.loader",
]
for _mod in _HA_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = ModuleType(_mod)

# homeassistant.const
_m = sys.modules["homeassistant.const"]
for attr in ("Platform", "UnitOfLength", "UnitOfMass", "UnitOfPower",
             "CONF_EMAIL", "CONF_PASSWORD"):
    setattr(_m, attr, MagicMock())
# homeassistant.core
_m = sys.modules["homeassistant.core"]
for attr in ("HomeAssistant", "ServiceCall"):
    setattr(_m, attr, MagicMock())
# homeassistant.exceptions
_m = sys.modules["homeassistant.exceptions"]
for attr in ("ConfigEntryAuthFailed", "HomeAssistantError"):
    setattr(_m, attr, type(attr, (Exception,), {}))
# homeassistant.config_entries
_m = sys.modules["homeassistant.config_entries"]
for attr in ("ConfigEntry", "ConfigFlow"):
    setattr(_m, attr, MagicMock())
# homeassistant.components.sensor
_m = sys.modules["homeassistant.components.sensor"]
for attr in ("SensorDeviceClass", "SensorEntity", "SensorEntityDescription", "SensorStateClass"):
    setattr(_m, attr, MagicMock())
# homeassistant.helpers.update_coordinator
_m = sys.modules["homeassistant.helpers.update_coordinator"]
setattr(_m, "DataUpdateCoordinator", MagicMock())
setattr(_m, "UpdateFailed", type("UpdateFailed", (Exception,), {}))
setattr(_m, "CoordinatorEntity", MagicMock())
# homeassistant.helpers.entity_platform
_m = sys.modules["homeassistant.helpers.entity_platform"]
setattr(_m, "AddEntitiesCallback", MagicMock())
# homeassistant.helpers.device_registry
_m = sys.modules["homeassistant.helpers.device_registry"]
for attr in ("DeviceEntryType", "DeviceInfo"):
    setattr(_m, attr, MagicMock())
# homeassistant.helpers.aiohttp_client
_m = sys.modules["homeassistant.helpers.aiohttp_client"]
for attr in ("async_get_clientsession", "async_create_clientsession"):
    setattr(_m, attr, MagicMock())
# homeassistant.loader
_m = sys.modules["homeassistant.loader"]
for attr in ("async_get_loaded_integration", "Integration"):
    setattr(_m, attr, MagicMock())

from custom_components.rouvy.api import RouvyAsyncApiClient


class _FakeResponse:
    """Lightweight mock for aiohttp.ClientResponse used as async context manager."""

    def __init__(self, status: int, body: str = "", cookies: dict | None = None):
        self.status = status
        self._body = body
        self._cookies = {}
        if cookies:
            for k, v in cookies.items():
                mock_cookie = MagicMock()
                mock_cookie.value = v
                self._cookies[k] = mock_cookie

    @property
    def cookies(self):
        return self._cookies

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_session(*responses: _FakeResponse) -> MagicMock:
    """Create a mock aiohttp.ClientSession that returns responses in order."""
    session = MagicMock()
    call_iter = iter(responses)

    def _post(*args, **kwargs):
        return next(call_iter)

    def _get(*args, **kwargs):
        return next(call_iter)

    def _request(*args, **kwargs):
        return next(call_iter)

    session.post = MagicMock(side_effect=_post)
    session.get = MagicMock(side_effect=_get)
    session.request = MagicMock(side_effect=_request)
    return session


# ===================================================================
# async_login
# ===================================================================


class TestAsyncLogin:
    """Verify async authentication flow."""

    @pytest.mark.asyncio
    async def test_successful_login_sets_authenticated(self) -> None:
        session = _make_session(
            _FakeResponse(200, body="ok", cookies={"session": "abc"}),
            _FakeResponse(200, body="ok", cookies={"csrf": "xyz"}),
        )
        client = RouvyAsyncApiClient("user@test.com", "pass", session)
        await client.async_login()
        assert client._authenticated is True, (
            "Expected _authenticated=True after successful login"
        )

    @pytest.mark.asyncio
    async def test_successful_login_captures_cookies(self) -> None:
        session = _make_session(
            _FakeResponse(200, cookies={"session": "abc"}),
            _FakeResponse(200, cookies={"csrf": "xyz"}),
        )
        client = RouvyAsyncApiClient("user@test.com", "pass", session)
        await client.async_login()
        assert "session" in client._cookies, (
            f"Expected 'session' cookie captured, got {client._cookies}"
        )
        assert "csrf" in client._cookies, (
            f"Expected 'csrf' cookie captured, got {client._cookies}"
        )

    @pytest.mark.asyncio
    async def test_login_failure_raises_auth_error(self) -> None:
        session = _make_session(
            _FakeResponse(401, body="unauthorized"),
        )
        client = RouvyAsyncApiClient("user@test.com", "wrong", session)
        with pytest.raises(AuthenticationError, match="Login failed"):
            await client.async_login()

    @pytest.mark.asyncio
    async def test_root_data_failure_raises_auth_error(self) -> None:
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # login OK
            _FakeResponse(500),  # root.data fails
        )
        client = RouvyAsyncApiClient("user@test.com", "pass", session)
        with pytest.raises(AuthenticationError, match="Session initialization"):
            await client.async_login()


# ===================================================================
# _request
# ===================================================================


class TestAsyncRequest:
    """Verify authenticated request logic."""

    @pytest.mark.asyncio
    async def test_auto_login_on_first_request(self) -> None:
        turbo = json.dumps(["email", "u@e.com", "userProfile", {"userName": "t"}])
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # login
            _FakeResponse(200, cookies={}),  # root
            _FakeResponse(200, body=turbo),  # actual request
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        text = await client._request("GET", "user-settings.data")
        assert "userProfile" in text, (
            f"Expected turbo-stream response, got {text[:100]}"
        )
        assert client._authenticated is True, (
            "Expected authenticated after auto-login"
        )

    @pytest.mark.asyncio
    async def test_401_triggers_reauth_and_retry(self) -> None:
        turbo = json.dumps(["email", "u@e.com", "userProfile", {"userName": "t"}])
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # initial login
            _FakeResponse(200, cookies={}),  # initial root
            _FakeResponse(401),  # first request → 401
            _FakeResponse(200, cookies={"s": "v2"}),  # re-login
            _FakeResponse(200, cookies={}),  # re-root
            _FakeResponse(200, body=turbo),  # retry succeeds
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        text = await client._request("GET", "user-settings.data")
        assert "userProfile" in text, (
            "Expected successful response after re-auth"
        )

    @pytest.mark.asyncio
    async def test_non_401_error_raises(self) -> None:
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # login
            _FakeResponse(200, cookies={}),  # root
            _FakeResponse(500, body="Server Error"),  # request fails
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        with pytest.raises(RouvyApiError, match="500"):
            await client._request("GET", "bad-endpoint")


# ===================================================================
# Typed accessor methods
# ===================================================================


class TestAsyncTypedAccessors:
    """Verify async typed accessor methods return correct model types."""

    def _pre_auth_client(self, session: MagicMock) -> RouvyAsyncApiClient:
        """Create a client that's already authenticated."""
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        return client

    @pytest.mark.asyncio
    async def test_get_user_profile_returns_model(self) -> None:
        turbo = json.dumps([
            "email", "u@e.com",
            "userProfile", {
                "userName": "testuser", "userId": "1",
                "firstName": "T", "lastName": "U",
                "ftp": 200, "ftpSource": "MANUAL",
                "weight": 80, "height": 175,
                "gender": "MALE", "maxHeartRate": 185,
                "countryIsoCode": "US", "timezone": "UTC",
                "units": "METRIC", "accountPrivacy": "PUBLIC",
            },
        ])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        profile = await client.async_get_user_profile()
        assert isinstance(profile, UserProfile), (
            f"Expected UserProfile, got {type(profile)}"
        )
        assert profile.username == "testuser", (
            f"Expected username testuser, got {profile.username}"
        )

    @pytest.mark.asyncio
    async def test_get_training_zones_returns_model(self) -> None:
        from rouvy_api_client.models import TrainingZones
        turbo = json.dumps([
            "userProfile", {"ftp": 250, "maxHeartRate": 195},
            "zones", {
                "power": {"values": [55, 75], "defaultValues": [55, 75]},
                "heartRate": {"values": [60, 65], "defaultValues": [60, 65]},
            },
        ])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        zones = await client.async_get_training_zones()
        assert isinstance(zones, TrainingZones), (
            f"Expected TrainingZones, got {type(zones)}"
        )
        assert zones.ftp_watts == 250, (
            f"Expected ftp 250, got {zones.ftp_watts}"
        )

    @pytest.mark.asyncio
    async def test_get_connected_apps_returns_list(self) -> None:
        from rouvy_api_client.models import ConnectedApp
        turbo = json.dumps([
            "activeProviders", [
                {"providerId": "strava", "name": "Strava", "status": "active"},
            ],
            "availableProviders", [],
        ])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        apps = await client.async_get_connected_apps()
        assert len(apps) == 1, f"Expected 1 app, got {len(apps)}"
        assert isinstance(apps[0], ConnectedApp), (
            f"Expected ConnectedApp, got {type(apps[0])}"
        )

    @pytest.mark.asyncio
    async def test_get_activity_summary_returns_model(self) -> None:
        from rouvy_api_client.models import ActivitySummary
        turbo = json.dumps([
            "activities", [{
                "id": "a1", "title": "Ride", "trainingType": "WORKOUT",
                "total": {"distance": 10000, "movingTime": 1800, "elevationGain": 0},
            }],
        ])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        summary = await client.async_get_activity_summary()
        assert isinstance(summary, ActivitySummary), (
            f"Expected ActivitySummary, got {type(summary)}"
        )


# ===================================================================
# async_validate_credentials
# ===================================================================


class TestAsyncValidateCredentials:
    """Verify credential validation helper."""

    @pytest.mark.asyncio
    async def test_valid_credentials_return_true(self) -> None:
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),
            _FakeResponse(200, cookies={}),
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        result = await client.async_validate_credentials()
        assert result is True, "Expected True for valid credentials"

    @pytest.mark.asyncio
    async def test_invalid_credentials_return_false(self) -> None:
        session = _make_session(
            _FakeResponse(401),
        )
        client = RouvyAsyncApiClient("u@e.com", "wrong", session)
        result = await client.async_validate_credentials()
        assert result is False, "Expected False for invalid credentials"


# ===================================================================
# async_update_user_settings
# ===================================================================


class TestAsyncUpdateUserSettings:
    """Verify async settings update."""

    @pytest.mark.asyncio
    async def test_update_fetches_current_then_posts(self) -> None:
        turbo = json.dumps([
            "email", "u@e.com",
            "userProfile", {
                "userName": "t", "weight": 80, "height": 175,
                "units": "METRIC",
            },
        ])
        session = _make_session(
            _FakeResponse(200, body=turbo),  # GET current
            _FakeResponse(200, body="ok"),  # POST update
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        await client.async_update_user_settings({"weight": 85})
        # Verify 2 requests were made (GET + POST)
        assert session.request.call_count == 2, (
            f"Expected 2 requests (GET + POST), got {session.request.call_count}"
        )
