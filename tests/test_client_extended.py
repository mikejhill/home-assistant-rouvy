"""Extended client tests.

Covers update_user_settings, convenience methods, URL building,
redirect detection, and 202 handling.
"""

from __future__ import annotations

import json

import pytest
import responses

from custom_components.rouvy.api_client import (
    ApiResponseError,
    RouvyClient,
    RouvyConfig,
)

AUTH_URL = "https://riders.rouvy.com/login.data"
ROOT_URL = "https://riders.rouvy.com/_root.data"
SETTINGS_URL = "https://riders.rouvy.com/user-settings.data"
ZONES_URL = "https://riders.rouvy.com/user-settings/zones.data"
APPS_URL = "https://riders.rouvy.com/user-settings/connected-apps.data"
OVERVIEW_URL = "https://riders.rouvy.com/profile/overview.data"
UPDATE_URL = "https://riders.rouvy.com/user-settings.data?index"


def _make_client() -> RouvyClient:
    return RouvyClient(RouvyConfig(email="u@e.com", password="pw"))


def _stub_auth() -> None:
    """Add auth stubs (login + root) to the responses mock."""
    responses.add(responses.POST, AUTH_URL, json={"ok": True}, status=200)
    responses.add(responses.GET, ROOT_URL, json={"ok": True}, status=200)


def _turbo_profile(**overrides: object) -> str:
    """Build a minimal turbo-stream user-settings response."""
    profile = {
        "userName": "testuser",
        "userId": "uid-1",
        "firstName": "Test",
        "lastName": "User",
        "ftp": 200,
        "ftpSource": "MANUAL",
        "weight": 80.0,
        "height": 175.0,
        "gender": "MALE",
        "maxHeartRate": 185,
        "countryIsoCode": "US",
        "timezone": "UTC",
        "units": "METRIC",
        "accountPrivacy": "PUBLIC",
    }
    profile.update(overrides)
    return json.dumps(["email", "u@e.com", "userProfile", profile])


# ===================================================================
# _build_url
# ===================================================================


class TestBuildUrl:
    """Verify internal URL construction."""

    def test_relative_path(self) -> None:
        client = _make_client()
        assert client._build_url("user-settings.data") == (
            "https://riders.rouvy.com/user-settings.data"
        ), "Expected base URL + relative path"

    def test_relative_path_with_leading_slash(self) -> None:
        client = _make_client()
        assert client._build_url("/user-settings.data") == (
            "https://riders.rouvy.com/user-settings.data"
        ), "Expected leading slash normalized"

    def test_absolute_url_passthrough(self) -> None:
        client = _make_client()
        url = "https://other.example.com/api"
        assert client._build_url(url) == url, "Expected absolute URL returned unchanged"

    def test_http_url_passthrough(self) -> None:
        client = _make_client()
        url = "http://localhost:8080/test"
        assert client._build_url(url) == url, "Expected http:// URL returned unchanged"


# ===================================================================
# _is_redirect_response
# ===================================================================


class TestIsRedirectResponse:
    """Verify SingleFetchRedirect detection."""

    @responses.activate
    def test_true_for_redirect_payload(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json=[["SingleFetchRedirect", 1]],
            status=202,
        )
        client = _make_client()
        client.login()
        resp = client._send_request("GET", SETTINGS_URL)
        assert client._is_redirect_response(resp) is True, (
            "Expected True for SingleFetchRedirect payload"
        )

    @responses.activate
    def test_false_for_normal_payload(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json={"data": "normal"},
            status=200,
        )
        client = _make_client()
        client.login()
        resp = client._send_request("GET", SETTINGS_URL)
        assert client._is_redirect_response(resp) is False, "Expected False for normal payload"

    @responses.activate
    def test_false_for_non_json_body(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body="not json",
            status=200,
        )
        client = _make_client()
        client.login()
        resp = client._send_request("GET", SETTINGS_URL)
        assert client._is_redirect_response(resp) is False, "Expected False when body is not JSON"


# ===================================================================
# 202 redirect handling
# ===================================================================


class TestHandle202Redirect:
    """Verify the 202 + SingleFetchRedirect retry logic."""

    @responses.activate
    def test_202_redirect_retries_after_root_data(self) -> None:
        _stub_auth()
        # First request: 202 redirect
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json=[["SingleFetchRedirect", 1]],
            status=202,
        )
        # Root data re-initialization
        responses.add(responses.GET, ROOT_URL, json={"ok": True}, status=200)
        # Retry succeeds
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body=_turbo_profile(),
            status=200,
        )
        client = _make_client()
        resp = client.get(SETTINGS_URL)
        assert resp.status_code == 200, f"Expected 200 after retry, got {resp.status_code}"

    @responses.activate
    def test_repeated_202_raises_api_response_error(self) -> None:
        _stub_auth()
        # Both requests: 202 redirect
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json=[["SingleFetchRedirect", 1]],
            status=202,
        )
        responses.add(responses.GET, ROOT_URL, json={"ok": True}, status=200)
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json=[["SingleFetchRedirect", 1]],
            status=202,
        )
        client = _make_client()
        with pytest.raises(ApiResponseError, match="unknown authentication state"):
            client.get(SETTINGS_URL)

    @responses.activate
    def test_202_root_data_failure_raises(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json=[["SingleFetchRedirect", 1]],
            status=202,
        )
        responses.add(responses.GET, ROOT_URL, json={"err": True}, status=500)
        client = _make_client()
        with pytest.raises(ApiResponseError, match="Session initialization failed"):
            client.get(SETTINGS_URL)


# ===================================================================
# update_user_settings
# ===================================================================


class TestUpdateUserSettings:
    """Verify the update_user_settings method."""

    @responses.activate
    def test_successful_update_posts_merged_payload(self) -> None:
        _stub_auth()
        # GET current settings
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body=_turbo_profile(),
            status=200,
        )
        # POST update
        responses.add(responses.POST, UPDATE_URL, json={"ok": True}, status=200)

        client = _make_client()
        resp = client.update_user_settings({"weight": 90})
        assert resp.status_code == 200, f"Expected 200 from update, got {resp.status_code}"
        # Verify POST was called
        post_calls = [
            c for c in responses.calls if c.request.method == "POST" and "index" in c.request.url
        ]
        assert len(post_calls) == 1, f"Expected 1 POST to update URL, got {len(post_calls)}"
        # Verify payload contains weight=90
        body = post_calls[0].request.body
        assert "weight=90" in body, f"Expected weight=90 in POST body, got {body}"

    @responses.activate
    def test_update_merges_with_current_settings(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body=_turbo_profile(weight=80.0, height=175.0),
            status=200,
        )
        responses.add(responses.POST, UPDATE_URL, json={"ok": True}, status=200)

        client = _make_client()
        client.update_user_settings({"weight": 85})
        post_calls = [
            c for c in responses.calls if c.request.method == "POST" and "index" in c.request.url
        ]
        body = post_calls[0].request.body
        # Height should still be present from current settings
        assert "height=175" in body, f"Expected current height preserved in POST, got {body}"
        assert "weight=85" in body, f"Expected updated weight=85 in POST, got {body}"

    @responses.activate
    def test_update_includes_intent(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body=_turbo_profile(),
            status=200,
        )
        responses.add(responses.POST, UPDATE_URL, json={"ok": True}, status=200)

        client = _make_client()
        client.update_user_settings({"weight": 80})
        post_calls = [
            c for c in responses.calls if c.request.method == "POST" and "index" in c.request.url
        ]
        body = post_calls[0].request.body
        assert "intent=update-units" in body, f"Expected intent=update-units in POST, got {body}"


# ===================================================================
# Convenience methods
# ===================================================================


class TestConvenienceMethods:
    """Verify typed convenience methods on RouvyClient."""

    @responses.activate
    def test_get_user_profile_returns_model(self) -> None:
        from custom_components.rouvy.api_client.models import UserProfile

        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body=_turbo_profile(),
            status=200,
        )
        client = _make_client()
        profile = client.get_user_profile()
        assert isinstance(profile, UserProfile), f"Expected UserProfile, got {type(profile)}"
        assert profile.username == "testuser", f"Expected username testuser, got {profile.username}"

    @responses.activate
    def test_get_training_zones_returns_model(self) -> None:
        from custom_components.rouvy.api_client.models import TrainingZones

        _stub_auth()
        zones_data = json.dumps(
            [
                "userProfile",
                {"ftp": 200, "maxHeartRate": 190},
                "zones",
                {
                    "power": {"values": [55, 75, 90], "defaultValues": [55, 75, 90]},
                    "heartRate": {"values": [60, 65, 75], "defaultValues": [60, 65, 75]},
                },
            ]
        )
        responses.add(responses.GET, ZONES_URL, body=zones_data, status=200)
        client = _make_client()
        zones = client.get_training_zones()
        assert isinstance(zones, TrainingZones), f"Expected TrainingZones, got {type(zones)}"
        assert zones.ftp_watts == 200, f"Expected ftp 200, got {zones.ftp_watts}"

    @responses.activate
    def test_get_connected_apps_returns_list(self) -> None:
        from custom_components.rouvy.api_client.models import ConnectedApp

        _stub_auth()
        apps_data = json.dumps(
            [
                "activeProviders",
                [
                    {"providerId": "garmin", "name": "Garmin", "status": "active"},
                ],
                "availableProviders",
                [],
            ]
        )
        responses.add(responses.GET, APPS_URL, body=apps_data, status=200)
        client = _make_client()
        apps = client.get_connected_apps()
        assert len(apps) == 1, f"Expected 1 app, got {len(apps)}"
        assert isinstance(apps[0], ConnectedApp), f"Expected ConnectedApp, got {type(apps[0])}"

    @responses.activate
    def test_get_activity_summary_returns_model(self) -> None:
        from custom_components.rouvy.api_client.models import ActivitySummary

        _stub_auth()
        act_data = json.dumps(
            [
                "activities",
                [
                    {
                        "id": "a1",
                        "title": "Ride",
                        "trainingType": "WORKOUT",
                        "total": {"distance": 10000, "movingTime": 1800, "elevationGain": 100},
                    }
                ],
            ]
        )
        responses.add(responses.GET, OVERVIEW_URL, body=act_data, status=200)
        client = _make_client()
        summary = client.get_activity_summary()
        assert isinstance(summary, ActivitySummary), (
            f"Expected ActivitySummary, got {type(summary)}"
        )
        assert len(summary.recent_activities) == 1, (
            f"Expected 1 activity, got {len(summary.recent_activities)}"
        )


# ===================================================================
# Error handling
# ===================================================================


class TestClientErrorHandling:
    """Verify error responses raise appropriate exceptions."""

    @responses.activate
    def test_400_raises_api_response_error(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json={"error": "bad request"},
            status=400,
        )
        client = _make_client()
        with pytest.raises(ApiResponseError) as exc_info:
            client.get(SETTINGS_URL)
        assert exc_info.value.status_code == 400, (
            f"Expected status 400, got {exc_info.value.status_code}"
        )

    @responses.activate
    def test_500_raises_api_response_error(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            json={"error": "internal"},
            status=500,
        )
        client = _make_client()
        with pytest.raises(ApiResponseError) as exc_info:
            client.get(SETTINGS_URL)
        assert exc_info.value.status_code == 500, (
            f"Expected status 500, got {exc_info.value.status_code}"
        )
        assert exc_info.value.payload == {"error": "internal"}, (
            f"Expected payload preserved, got {exc_info.value.payload}"
        )

    @responses.activate
    def test_non_json_error_body_captured_as_text(self) -> None:
        _stub_auth()
        responses.add(
            responses.GET,
            SETTINGS_URL,
            body="Server Error",
            status=500,
        )
        client = _make_client()
        with pytest.raises(ApiResponseError) as exc_info:
            client.get(SETTINGS_URL)
        assert exc_info.value.payload == "Server Error", (
            f"Expected text payload, got {exc_info.value.payload}"
        )
