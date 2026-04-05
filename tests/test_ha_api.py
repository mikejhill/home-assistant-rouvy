"""Tests for the Home Assistant async API client.

Uses pytest-asyncio and unittest.mock to test RouvyAsyncApiClient
without requiring a live Rouvy API or network access.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from custom_components.rouvy.api import RouvyAsyncApiClient
from custom_components.rouvy.api_client.errors import AuthenticationError, RouvyApiError
from custom_components.rouvy.api_client.models import UserProfile


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
        assert client._authenticated is True, "Expected _authenticated=True after successful login"

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
        assert "csrf" in client._cookies, f"Expected 'csrf' cookie captured, got {client._cookies}"

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
        assert "userProfile" in text, f"Expected turbo-stream response, got {text[:100]}"
        assert client._authenticated is True, "Expected authenticated after auto-login"

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
        assert "userProfile" in text, "Expected successful response after re-auth"

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

    @pytest.mark.asyncio
    async def test_202_redirect_triggers_reauth_and_retry(self) -> None:
        """Verify that a 202 response with SingleFetchRedirect body re-authenticates."""
        redirect_body = json.dumps([["SingleFetchRedirect", 1]])
        turbo = json.dumps(["email", "u@e.com", "userProfile", {"userName": "t"}])
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # initial login
            _FakeResponse(200, cookies={}),  # initial root
            _FakeResponse(202, body=redirect_body),  # request → 202 redirect
            _FakeResponse(200, cookies={"s": "v2"}),  # re-login
            _FakeResponse(200, cookies={}),  # re-root
            _FakeResponse(200, body=turbo),  # retry succeeds
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        text = await client._request("GET", "user-settings.data")
        assert "userProfile" in text, "Expected successful response after 202 redirect re-auth"

    @pytest.mark.asyncio
    async def test_202_non_redirect_body_raises_error(self) -> None:
        """Verify that a 202 without redirect body returns normally."""
        normal_body = json.dumps({"status": "accepted"})
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # login
            _FakeResponse(200, cookies={}),  # root
            _FakeResponse(202, body=normal_body),  # 202 but not a redirect
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        text = await client._request("GET", "some-endpoint")
        assert "accepted" in text, "Expected 202 non-redirect body returned as-is"

    @pytest.mark.asyncio
    async def test_retry_failure_after_401_raises(self) -> None:
        """Verify that if retry after re-auth also fails, an error is raised."""
        session = _make_session(
            _FakeResponse(200, cookies={"s": "v"}),  # initial login
            _FakeResponse(200, cookies={}),  # initial root
            _FakeResponse(401),  # first request → 401
            _FakeResponse(200, cookies={"s": "v2"}),  # re-login
            _FakeResponse(200, cookies={}),  # re-root
            _FakeResponse(500, body="Server Error"),  # retry also fails
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        with pytest.raises(RouvyApiError, match="after re-auth"):
            await client._request("GET", "user-settings.data")


# ===================================================================
# _is_redirect_body
# ===================================================================


class TestIsRedirectBody:
    """Verify redirect body detection."""

    def test_valid_redirect_body(self) -> None:
        body = json.dumps([["SingleFetchRedirect", 1]])
        assert RouvyAsyncApiClient._is_redirect_body(body) is True

    def test_non_redirect_list(self) -> None:
        body = json.dumps([["SomethingElse", 1]])
        assert RouvyAsyncApiClient._is_redirect_body(body) is False

    def test_empty_list(self) -> None:
        assert RouvyAsyncApiClient._is_redirect_body("[]") is False

    def test_non_json(self) -> None:
        assert RouvyAsyncApiClient._is_redirect_body("<html>not json</html>") is False

    def test_object_not_list(self) -> None:
        assert RouvyAsyncApiClient._is_redirect_body('{"key": "value"}') is False


# ===================================================================
# Cookie clearing on re-login
# ===================================================================


class TestCookieClearing:
    """Verify that cookies are cleared on re-login."""

    @pytest.mark.asyncio
    async def test_login_clears_stale_cookies(self) -> None:
        """Verify that async_login clears cookies before establishing a new session."""
        session = _make_session(
            _FakeResponse(200, cookies={"session": "first"}),
            _FakeResponse(200, cookies={"csrf": "first"}),
            _FakeResponse(200, cookies={"session": "second"}),
            _FakeResponse(200, cookies={"csrf": "second"}),
        )
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        # First login
        await client.async_login()
        assert client._cookies["session"] == "first"
        # Second login should clear and replace
        await client.async_login()
        assert client._cookies["session"] == "second"
        assert client._cookies["csrf"] == "second"


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
        turbo = json.dumps(
            [
                "email",
                "u@e.com",
                "userProfile",
                {
                    "userName": "testuser",
                    "userId": "1",
                    "firstName": "T",
                    "lastName": "U",
                    "ftp": 200,
                    "ftpSource": "MANUAL",
                    "weight": 80,
                    "height": 175,
                    "gender": "MALE",
                    "maxHeartRate": 185,
                    "countryIsoCode": "US",
                    "timezone": "UTC",
                    "units": "METRIC",
                    "accountPrivacy": "PUBLIC",
                },
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        profile = await client.async_get_user_profile()
        assert isinstance(profile, UserProfile), f"Expected UserProfile, got {type(profile)}"
        assert profile.username == "testuser", f"Expected username testuser, got {profile.username}"

    @pytest.mark.asyncio
    async def test_get_training_zones_returns_model(self) -> None:
        from custom_components.rouvy.api_client.models import TrainingZones

        turbo = json.dumps(
            [
                "userProfile",
                {"ftp": 250, "maxHeartRate": 195},
                "zones",
                {
                    "power": {"values": [55, 75], "defaultValues": [55, 75]},
                    "heartRate": {"values": [60, 65], "defaultValues": [60, 65]},
                },
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        zones = await client.async_get_training_zones()
        assert isinstance(zones, TrainingZones), f"Expected TrainingZones, got {type(zones)}"
        assert zones.ftp_watts == 250, f"Expected ftp 250, got {zones.ftp_watts}"

    @pytest.mark.asyncio
    async def test_get_connected_apps_returns_list(self) -> None:
        from custom_components.rouvy.api_client.models import ConnectedApp

        turbo = json.dumps(
            [
                "activeProviders",
                [
                    {"providerId": "strava", "name": "Strava", "status": "active"},
                ],
                "availableProviders",
                [],
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        apps = await client.async_get_connected_apps()
        assert len(apps) == 1, f"Expected 1 app, got {len(apps)}"
        assert isinstance(apps[0], ConnectedApp), f"Expected ConnectedApp, got {type(apps[0])}"

    @pytest.mark.asyncio
    async def test_get_activity_summary_returns_model(self) -> None:
        from custom_components.rouvy.api_client.models import ActivitySummary

        turbo = json.dumps(
            [
                "activities",
                [
                    {
                        "id": "a1",
                        "title": "Ride",
                        "trainingType": "WORKOUT",
                        "total": {"distance": 10000, "movingTime": 1800, "elevationGain": 0},
                    }
                ],
            ]
        )
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
        turbo = json.dumps(
            [
                "email",
                "u@e.com",
                "userProfile",
                {
                    "userName": "t",
                    "weight": 80,
                    "height": 175,
                    "units": "METRIC",
                },
            ]
        )
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


# ===================================================================
# async_get_activity_stats
# ===================================================================


class TestAsyncGetActivityStats:
    """Verify async activity stats fetching."""

    @staticmethod
    def _pre_auth_client(session: MagicMock) -> RouvyAsyncApiClient:
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        return client

    @pytest.mark.asyncio
    async def test_returns_weekly_stats_list(self) -> None:
        from custom_components.rouvy.api_client.models import WeeklyActivityStats

        turbo = json.dumps(
            [
                {},
                "activityStats",
                {
                    "0": {
                        "weekStart": "Mar 30, 2026",
                        "weekEnd": "Apr 5, 2026",
                        "activityTypeStats": {
                            "ride": {
                                "distM": 50000.0,
                                "elevM": 400.0,
                                "kCal": 900.0,
                                "movingTimeSec": 6000,
                                "if": 0.75,
                                "trainingScore": 70.0,
                                "activityCount": 4,
                            }
                        },
                    }
                },
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        stats = await client.async_get_activity_stats(2026, 4)
        assert len(stats) == 1, f"Expected 1 week, got {len(stats)}"
        assert isinstance(stats[0], WeeklyActivityStats)
        assert stats[0].ride.distance_m == 50000.0
        assert stats[0].ride.activity_count == 4

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self) -> None:
        turbo = json.dumps([{}])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        stats = await client.async_get_activity_stats(2026, 4)
        assert stats == [], f"Expected empty list, got {stats}"


# ===================================================================
# async_get_challenges
# ===================================================================


class TestAsyncGetChallenges:
    """Verify async challenge fetching."""

    @staticmethod
    def _pre_auth_client(session: MagicMock) -> RouvyAsyncApiClient:
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        return client

    @pytest.mark.asyncio
    async def test_returns_challenge_list(self) -> None:
        from custom_components.rouvy.api_client.models import Challenge

        turbo = json.dumps(
            [
                "challenges",
                [
                    {
                        "id": "spring-2026",
                        "userStatus": "joined",
                        "state": "active",
                        "registeredCount": 500,
                        "registered": True,
                        "title": "Spring 2026",
                        "logo": "",
                        "experience": 300,
                        "coins": 50,
                        "startDateTime": "2026-03-01T00:00:00Z",
                        "endDateTime": "2026-04-01T00:00:00Z",
                        "isPast": False,
                        "isUpcoming": False,
                        "isDone": False,
                        "segments": [],
                    }
                ],
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        challenges = await client.async_get_challenges()
        assert len(challenges) == 1
        assert isinstance(challenges[0], Challenge)
        assert challenges[0].id == "spring-2026"
        assert challenges[0].registered is True

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self) -> None:
        turbo = json.dumps(["challenges", []])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        challenges = await client.async_get_challenges()
        assert challenges == []


# ===================================================================
# async_register_challenge
# ===================================================================


class TestAsyncRegisterChallenge:
    """Verify async challenge registration."""

    @staticmethod
    def _pre_auth_client(session: MagicMock) -> RouvyAsyncApiClient:
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        return client

    @pytest.mark.asyncio
    async def test_successful_registration_returns_true(self) -> None:
        body = json.dumps({"ok": True, "error": None})
        session = _make_session(_FakeResponse(200, body=body))
        client = self._pre_auth_client(session)
        result = await client.async_register_challenge("spring-2026")
        assert result is True

    @pytest.mark.asyncio
    async def test_failed_registration_returns_false(self) -> None:
        body = json.dumps({"ok": False, "error": "already_registered"})
        session = _make_session(_FakeResponse(200, body=body))
        client = self._pre_auth_client(session)
        result = await client.async_register_challenge("spring-2026")
        assert result is False

    @pytest.mark.asyncio
    async def test_non_json_response_returns_false(self) -> None:
        session = _make_session(_FakeResponse(200, body="not json"))
        client = self._pre_auth_client(session)
        result = await client.async_register_challenge("spring-2026")
        assert result is False


# ===================================================================
# async_get_favorite_routes
# ===================================================================


class TestAsyncGetFavoriteRoutes:
    """Verify async favorite routes fetching."""

    @staticmethod
    def _pre_auth_client(session: MagicMock) -> RouvyAsyncApiClient:
        client = RouvyAsyncApiClient("u@e.com", "pw", session)
        client._authenticated = True
        return client

    @pytest.mark.asyncio
    async def test_returns_only_favorites(self) -> None:
        from custom_components.rouvy.api_client.models import Route

        turbo = json.dumps(
            [
                "routes",
                [
                    {
                        "id": 1,
                        "name": "Favorite Route",
                        "distanceInMeters": 10000.0,
                        "elevationInMeters": 100.0,
                        "estimatedTime": 1800,
                        "rating": 4.0,
                        "countryCodeISO": "CZ",
                        "favorite": True,
                        "completedDistanceMeters": 10000.0,
                        "onlineCount": 3,
                        "coinsForCompletion": 20,
                    },
                    {
                        "id": 2,
                        "name": "Non-Favorite",
                        "distanceInMeters": 20000.0,
                        "elevationInMeters": 200.0,
                        "estimatedTime": 3600,
                        "rating": 3.0,
                        "countryCodeISO": "DE",
                        "favorite": False,
                        "completedDistanceMeters": 0.0,
                        "onlineCount": 1,
                        "coinsForCompletion": 10,
                    },
                ],
            ]
        )
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        favorites = await client.async_get_favorite_routes()
        assert len(favorites) == 1
        assert isinstance(favorites[0], Route)
        assert favorites[0].route_id == 1
        assert favorites[0].favorite is True

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self) -> None:
        turbo = json.dumps(["routes", []])
        session = _make_session(_FakeResponse(200, body=turbo))
        client = self._pre_auth_client(session)
        favorites = await client.async_get_favorite_routes()
        assert favorites == []
