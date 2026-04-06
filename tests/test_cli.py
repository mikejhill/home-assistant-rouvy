"""Tests for CLI utility functions, argument parsing, and async command handlers.

Tests pure functions and async handlers from __main__.py without requiring
live API access or environment variables. All API interactions are mocked.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.rouvy.api_client.__main__ import (
    _coerce_value,
    _format_profile_field,
    _format_time,
    _parse_settings,
    load_credentials,
)
from custom_components.rouvy.api_client.models import (
    Activity,
    ActivitySummary,
    ActivityTypeStats,
    CareerStats,
    Challenge,
    ConnectedApp,
    Event,
    FriendsSummary,
    Route,
    TrainingZones,
    UserProfile,
    WeeklyActivityStats,
)

_CLI_MOD = "custom_components.rouvy.api_client.__main__"


# ===================================================================
# Test data factories
# ===================================================================


def _mock_profile(**overrides: object) -> UserProfile:
    defaults: dict[str, object] = dict(
        email="user@test.com",
        username="tester",
        first_name="Test",
        last_name="User",
        weight_kg=80.0,
        height_cm=175.0,
        units="METRIC",
        ftp_watts=200,
        ftp_source="MANUAL",
        max_heart_rate=185,
        gender="MALE",
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _mock_zones(**overrides: object) -> TrainingZones:
    defaults: dict[str, object] = dict(
        ftp_watts=200,
        max_heart_rate=185,
        power_zone_values=[55, 75, 90, 105, 120, 150],
        power_zone_defaults=[55, 75, 90, 105, 120, 150],
        hr_zone_values=[60, 70, 80, 90, 95, 100],
        hr_zone_defaults=[60, 70, 80, 90, 95, 100],
    )
    defaults.update(overrides)
    return TrainingZones(**defaults)


def _mock_args(**overrides: object) -> argparse.Namespace:
    """Build an argparse.Namespace with common defaults."""
    defaults: dict[str, object] = dict(
        json_output=False,
        debug=False,
        log_level="WARNING",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run(coro: object) -> object:
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ===================================================================
# _coerce_value
# ===================================================================


class TestCoerceValue:
    """Verify type coercion for CLI KEY=VALUE settings."""

    def test_integer_string_becomes_int(self) -> None:
        result = _coerce_value("42")
        assert result == 42
        assert isinstance(result, int)

    def test_negative_integer_string_becomes_int(self) -> None:
        result = _coerce_value("-5")
        assert result == -5
        assert isinstance(result, int)

    def test_float_string_becomes_float(self) -> None:
        result = _coerce_value("3.14")
        assert result == 3.14
        assert isinstance(result, float)

    def test_plain_string_stays_string(self) -> None:
        result = _coerce_value("METRIC")
        assert result == "METRIC"
        assert isinstance(result, str)

    def test_zero_becomes_int(self) -> None:
        result = _coerce_value("0")
        assert result == 0
        assert isinstance(result, int)

    def test_empty_string_stays_string(self) -> None:
        result = _coerce_value("")
        assert result == ""
        assert isinstance(result, str)


# ===================================================================
# _parse_settings
# ===================================================================


class TestParseSettings:
    """Verify KEY=VALUE string parsing."""

    def test_single_setting_parsed(self) -> None:
        result = _parse_settings(["weight=86"])
        assert result == {"weight": 86}

    def test_multiple_settings_parsed(self) -> None:
        result = _parse_settings(["weight=86", "height=178"])
        assert result == {"weight": 86, "height": 178}

    def test_string_value_parsed(self) -> None:
        result = _parse_settings(["units=IMPERIAL"])
        assert result == {"units": "IMPERIAL"}

    def test_value_with_equals_sign(self) -> None:
        result = _parse_settings(["formula=a=b+c"])
        assert result["formula"] == "a=b+c"

    def test_invalid_format_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid format"):
            _parse_settings(["no_equals_here"])

    def test_float_value_parsed(self) -> None:
        result = _parse_settings(["weight=85.5"])
        assert result == {"weight": 85.5}


# ===================================================================
# _format_profile_field
# ===================================================================


class TestFormatProfileField:
    """Verify field name to human-readable label conversion."""

    def test_known_field_weight(self) -> None:
        assert _format_profile_field("weight_kg") == "Weight (kg)"

    def test_known_field_email(self) -> None:
        assert _format_profile_field("email") == "Email"

    def test_known_field_ftp(self) -> None:
        assert _format_profile_field("ftp_watts") == "FTP (watts)"

    def test_unknown_field_uses_title_case(self) -> None:
        assert _format_profile_field("custom_field_name") == "Custom Field Name"


# ===================================================================
# _format_time
# ===================================================================


class TestFormatTime:
    """Verify seconds-to-time string formatting."""

    def test_zero_seconds(self) -> None:
        assert _format_time(0) == "0:00"

    def test_seconds_only(self) -> None:
        assert _format_time(45) == "0:45"

    def test_minutes_and_seconds(self) -> None:
        assert _format_time(125) == "2:05"

    def test_hours_minutes_seconds(self) -> None:
        assert _format_time(3661) == "1:01:01"

    def test_exact_hour(self) -> None:
        assert _format_time(3600) == "1:00:00"

    def test_large_duration(self) -> None:
        assert _format_time(36000) == "10:00:00"


# ===================================================================
# load_credentials
# ===================================================================


class TestLoadCredentials:
    """Verify credential loading from environment."""

    @patch.dict(os.environ, {"ROUVY_EMAIL": "test@e.com", "ROUVY_PASSWORD": "pass123"})
    def test_returns_tuple_when_both_set(self) -> None:
        email, password = load_credentials()
        assert email == "test@e.com"
        assert password == "pass123"

    def test_raises_when_email_empty(self) -> None:
        with (
            patch.dict(os.environ, {"ROUVY_EMAIL": "", "ROUVY_PASSWORD": "pw"}, clear=False),
            pytest.raises(ValueError, match="ROUVY_EMAIL"),
        ):
            load_credentials()

    def test_raises_when_password_missing(self) -> None:
        with (
            patch.dict(os.environ, {"ROUVY_EMAIL": "a@b.com", "ROUVY_PASSWORD": ""}, clear=False),
            pytest.raises(ValueError, match="ROUVY_EMAIL"),
        ):
            load_credentials()


# ===================================================================
# Argument parsing
# ===================================================================


class TestParseArgs:
    """Verify argument parsing for subcommands."""

    def test_profile_subcommand(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "profile"]):
            args = _parse_args()
        assert args.subcommand == "profile"

    def test_zones_subcommand(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "zones"]):
            args = _parse_args()
        assert args.subcommand == "zones"

    def test_set_subcommand_with_settings(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "set", "weight=86", "height=178"]):
            args = _parse_args()
        assert args.subcommand == "set"
        assert args.settings == ["weight=86", "height=178"]

    def test_raw_subcommand_with_endpoint(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "raw", "user-settings.data"]):
            args = _parse_args()
        assert args.subcommand == "raw"
        assert args.raw_endpoint == "user-settings.data"

    def test_debug_flag(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "profile", "--debug"]):
            args = _parse_args()
        assert args.debug is True

    def test_json_flag(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy", "profile", "--json"]):
            args = _parse_args()
        assert args.json_output is True

    def test_default_no_subcommand_gets_profile_handler(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_profile, _parse_args

        with patch("sys.argv", ["rouvy"]):
            args = _parse_args()
        assert args.handler is _cmd_profile

    def test_new_subcommands_exist(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        for cmd in ["career", "challenges", "events", "friends", "routes", "activity-stats"]:
            extra = ["--year", "2026", "--month", "1"] if cmd == "activity-stats" else []
            with patch("sys.argv", ["rouvy", cmd, *extra]):
                args = _parse_args()
            assert args.subcommand == cmd, f"Subcommand '{cmd}' not parsed"

    def test_write_subcommands_exist(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        cases = [
            ["set-weight", "--weight", "80"],
            ["set-height", "--height", "175"],
            ["set-units", "--units", "METRIC"],
            ["set-ftp", "--source", "MANUAL", "--value", "250"],
            ["set-max-hr", "--max-hr", "185"],
            ["set-timezone", "--timezone", "UTC"],
            ["set-zones", "--type", "power", "--zones", "55,75,90,105,120,150"],
            ["register-challenge", "--slug", "test-challenge"],
            ["register-event", "--event-id", "abc-123"],
            ["unregister-event", "--event-id", "abc-123"],
        ]
        for argv in cases:
            with patch("sys.argv", ["rouvy", *argv]):
                args = _parse_args()
            assert args.subcommand == argv[0], f"Subcommand '{argv[0]}' not parsed"


# ===================================================================
# Async command handler tests
# ===================================================================


class TestCmdProfile:
    """Verify profile subcommand output."""

    def test_prints_profile_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_profile

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile()
        _run(_cmd_profile(client, _mock_args()))
        output = capsys.readouterr().out
        assert "USER PROFILE" in output

    def test_prints_weight(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_profile

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile(weight_kg=85.5)
        _run(_cmd_profile(client, _mock_args()))
        output = capsys.readouterr().out
        assert "85.5" in output

    def test_skips_none_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_profile

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile(
            gender=None,
            birth_date=None,
            country=None,
        )
        _run(_cmd_profile(client, _mock_args()))
        output = capsys.readouterr().out
        assert "Gender" not in output
        assert "Birth Date" not in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_profile

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile()
        _run(_cmd_profile(client, _mock_args(json_output=True)))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["username"] == "tester"
        assert data["weight_kg"] == 80.0


class TestCmdZones:
    """Verify zones subcommand output."""

    def test_prints_zones_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_zones

        client = AsyncMock()
        client.async_get_training_zones.return_value = _mock_zones()
        _run(_cmd_zones(client, _mock_args()))
        output = capsys.readouterr().out
        assert "TRAINING ZONES" in output

    def test_prints_ftp(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_zones

        client = AsyncMock()
        client.async_get_training_zones.return_value = _mock_zones(ftp_watts=250)
        _run(_cmd_zones(client, _mock_args()))
        output = capsys.readouterr().out
        assert "250" in output

    def test_prints_power_zone_labels(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_zones

        client = AsyncMock()
        client.async_get_training_zones.return_value = _mock_zones()
        _run(_cmd_zones(client, _mock_args()))
        output = capsys.readouterr().out
        for label in ["Recovery", "Endurance", "Tempo", "Threshold"]:
            assert label in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_zones

        client = AsyncMock()
        client.async_get_training_zones.return_value = _mock_zones()
        _run(_cmd_zones(client, _mock_args(json_output=True)))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["ftp_watts"] == 200
        assert len(data["power_zone_values"]) == 6


class TestCmdApps:
    """Verify connected apps subcommand output."""

    def test_prints_apps_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_apps

        client = AsyncMock()
        client.async_get_connected_apps.return_value = []
        _run(_cmd_apps(client, _mock_args()))
        output = capsys.readouterr().out
        assert "CONNECTED APPS" in output

    def test_connected_app_shows_checkmark(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_apps

        apps = [ConnectedApp(name="Strava", provider_id="strava", status="connected")]
        client = AsyncMock()
        client.async_get_connected_apps.return_value = apps
        _run(_cmd_apps(client, _mock_args()))
        output = capsys.readouterr().out
        assert "✓" in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_apps

        apps = [ConnectedApp(name="Strava", provider_id="strava", status="connected")]
        client = AsyncMock()
        client.async_get_connected_apps.return_value = apps
        _run(_cmd_apps(client, _mock_args(json_output=True)))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["name"] == "Strava"


class TestCmdActivities:
    """Verify activities subcommand output."""

    def test_no_activities_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_activities

        client = AsyncMock()
        client.async_get_activity_summary.return_value = ActivitySummary(recent_activities=[])
        _run(_cmd_activities(client, _mock_args()))
        output = capsys.readouterr().out
        assert "No recent activities" in output

    def test_activity_title_and_distance(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_activities

        act = Activity(
            activity_id="a1",
            title="Morning Ride",
            training_type="ROUTE",
            distance_m=25000.0,
            moving_time_seconds=3600,
            elevation_m=300.0,
            start_utc="2024-01-15",
        )
        client = AsyncMock()
        client.async_get_activity_summary.return_value = ActivitySummary(recent_activities=[act])
        _run(_cmd_activities(client, _mock_args()))
        output = capsys.readouterr().out
        assert "Morning Ride" in output
        assert "25.0 km" in output


class TestCmdCareer:
    """Verify career subcommand output."""

    def test_prints_career_stats(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_career

        career = CareerStats(
            level=25,
            experience_points=9500,
            coins=3200,
            total_activities=247,
            total_distance_m=4567800.0,
            total_elevation_m=45678.0,
            total_time_seconds=1125000,
            total_achievements=37,
            total_trophies=12,
        )
        client = AsyncMock()
        client.async_get_career.return_value = career
        _run(_cmd_career(client, _mock_args()))
        output = capsys.readouterr().out
        assert "CAREER STATS" in output
        assert "25" in output
        assert "9,500" in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_career

        career = CareerStats(level=10, coins=500)
        client = AsyncMock()
        client.async_get_career.return_value = career
        _run(_cmd_career(client, _mock_args(json_output=True)))
        data = json.loads(capsys.readouterr().out)
        assert data["level"] == 10
        assert data["coins"] == 500


class TestCmdChallenges:
    """Verify challenges subcommand output."""

    def test_no_challenges_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_challenges

        client = AsyncMock()
        client.async_get_challenges.return_value = []
        _run(_cmd_challenges(client, _mock_args()))
        output = capsys.readouterr().out
        assert "No challenges" in output

    def test_challenge_listed(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_challenges

        ch = Challenge(
            id="ch1",
            title="Summer Sprint",
            state="ACTIVE",
            registered=True,
            start_date_time="2026-06-01T00:00:00Z",
            end_date_time="2026-06-30T23:59:59Z",
        )
        client = AsyncMock()
        client.async_get_challenges.return_value = [ch]
        _run(_cmd_challenges(client, _mock_args()))
        output = capsys.readouterr().out
        assert "Summer Sprint" in output
        assert "Yes" in output


class TestCmdEvents:
    """Verify events subcommand output."""

    def test_no_events_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_events

        client = AsyncMock()
        client.async_get_events.return_value = []
        _run(_cmd_events(client, _mock_args()))
        output = capsys.readouterr().out
        assert "No upcoming events" in output

    def test_event_listed(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_events

        ev = Event(
            event_id="ev1",
            title="Saturday Race",
            event_type="RACE",
            start_date_time="2026-04-12T08:00:00Z",
            registered=False,
        )
        client = AsyncMock()
        client.async_get_events.return_value = [ev]
        _run(_cmd_events(client, _mock_args()))
        output = capsys.readouterr().out
        assert "Saturday Race" in output


class TestCmdFriends:
    """Verify friends subcommand output."""

    def test_prints_friend_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_friends

        client = AsyncMock()
        client.async_get_friends.return_value = FriendsSummary(total_friends=42, online_friends=5)
        _run(_cmd_friends(client, _mock_args()))
        output = capsys.readouterr().out
        assert "42" in output
        assert "5" in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_friends

        client = AsyncMock()
        client.async_get_friends.return_value = FriendsSummary(total_friends=10, online_friends=2)
        _run(_cmd_friends(client, _mock_args(json_output=True)))
        data = json.loads(capsys.readouterr().out)
        assert data["total_friends"] == 10


class TestCmdRoutes:
    """Verify routes subcommand output."""

    def test_no_routes_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_routes

        client = AsyncMock()
        client.async_get_favorite_routes.return_value = []
        _run(_cmd_routes(client, _mock_args()))
        output = capsys.readouterr().out
        assert "No favorite routes" in output

    def test_route_listed(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_routes

        route = Route(
            route_id=1,
            name="Col du Galibier",
            distance_m=34200.0,
            elevation_m=1245.0,
            country_code="FR",
            favorite=True,
        )
        client = AsyncMock()
        client.async_get_favorite_routes.return_value = [route]
        _run(_cmd_routes(client, _mock_args()))
        output = capsys.readouterr().out
        assert "Col du Galibier" in output
        assert "FR" in output


class TestCmdActivityStats:
    """Verify activity-stats subcommand output."""

    def test_no_stats_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_activity_stats

        client = AsyncMock()
        client.async_get_activity_stats.return_value = []
        args = _mock_args(year=2026, month=4)
        _run(_cmd_activity_stats(client, args))
        output = capsys.readouterr().out
        assert "No activity stats" in output

    def test_stats_display_ride_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_activity_stats

        week = WeeklyActivityStats(
            week_start="2026-04-07",
            week_end="2026-04-13",
            ride=ActivityTypeStats(
                distance_m=50000.0,
                activity_count=3,
                moving_time_seconds=5400,
                calories=1200.0,
            ),
        )
        client = AsyncMock()
        client.async_get_activity_stats.return_value = [week]
        args = _mock_args(year=2026, month=4)
        _run(_cmd_activity_stats(client, args))
        output = capsys.readouterr().out
        assert "2026-04-07" in output
        assert "3 activities" in output


# ===================================================================
# Write command handlers
# ===================================================================


class TestCmdSet:
    """Verify set subcommand with mocked client."""

    def test_successful_update(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile(weight_kg=86.0)
        args = _mock_args(settings=["weight=86"])
        _run(_cmd_set(client, args))
        output = capsys.readouterr().out
        assert "Settings updated" in output
        client.async_update_user_settings.assert_called_once()

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set

        client = AsyncMock()
        client.async_get_user_profile.return_value = _mock_profile()
        args = _mock_args(settings=["weight=86"], json_output=True)
        _run(_cmd_set(client, args))
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ok"


class TestCmdSetProfile:
    """Verify set-profile subcommand."""

    def test_updates_username(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_profile

        client = AsyncMock()
        args = _mock_args(
            username="NewName",
            first_name=None,
            last_name=None,
            team=None,
            country=None,
            privacy=None,
        )
        _run(_cmd_set_profile(client, args))
        output = capsys.readouterr().out
        assert "Profile updated" in output
        client.async_update_user_profile.assert_called_once()

    def test_updates_privacy(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_profile

        client = AsyncMock()
        args = _mock_args(
            username=None,
            first_name=None,
            last_name=None,
            team=None,
            country=None,
            privacy="PRIVATE",
        )
        _run(_cmd_set_profile(client, args))
        client.async_update_user_social.assert_called_once_with("PRIVATE")

    def test_raises_when_no_fields(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_profile

        client = AsyncMock()
        args = _mock_args(
            username=None,
            first_name=None,
            last_name=None,
            team=None,
            country=None,
            privacy=None,
        )
        with pytest.raises(ValueError, match="No profile fields"):
            _run(_cmd_set_profile(client, args))


class TestCmdSetWeight:
    """Verify set-weight subcommand."""

    def test_updates_weight(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_weight

        client = AsyncMock()
        args = _mock_args(weight=85.0)
        _run(_cmd_set_weight(client, args))
        output = capsys.readouterr().out
        assert "85.0" in output
        client.async_update_user_settings.assert_called_once_with({"weight": 85.0})


class TestCmdSetFtp:
    """Verify set-ftp subcommand."""

    def test_sets_manual_ftp(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_ftp

        client = AsyncMock()
        args = _mock_args(source="MANUAL", value=250)
        _run(_cmd_set_ftp(client, args))
        output = capsys.readouterr().out
        assert "MANUAL" in output
        assert "250" in output
        client.async_update_ftp.assert_called_once_with("MANUAL", 250)


class TestCmdSetMaxHr:
    """Verify set-max-hr subcommand."""

    def test_updates_max_hr(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_max_hr

        client = AsyncMock()
        args = _mock_args(max_hr=190)
        _run(_cmd_set_max_hr(client, args))
        output = capsys.readouterr().out
        assert "190" in output
        client.async_update_max_heart_rate.assert_called_once_with(190)


class TestCmdSetZones:
    """Verify set-zones subcommand."""

    def test_parses_and_updates_zones(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_set_zones

        client = AsyncMock()
        args = _mock_args(zone_type="power", zones="55,75,90,105,120,150")
        _run(_cmd_set_zones(client, args))
        client.async_update_zones.assert_called_once_with("power", [55, 75, 90, 105, 120, 150])


class TestCmdRegisterChallenge:
    """Verify register-challenge subcommand."""

    def test_successful_registration(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_register_challenge

        client = AsyncMock()
        client.async_register_challenge.return_value = True
        args = _mock_args(slug="summer-sprint")
        _run(_cmd_register_challenge(client, args))
        output = capsys.readouterr().out
        assert "✓" in output
        assert "summer-sprint" in output


class TestCmdRegisterEvent:
    """Verify register/unregister event subcommands."""

    def test_register_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_register_event

        client = AsyncMock()
        client.async_register_event.return_value = True
        args = _mock_args(event_id="ev-123")
        _run(_cmd_register_event(client, args))
        output = capsys.readouterr().out
        assert "✓" in output

    def test_unregister_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_unregister_event

        client = AsyncMock()
        client.async_unregister_event.return_value = True
        args = _mock_args(event_id="ev-123")
        _run(_cmd_unregister_event(client, args))
        output = capsys.readouterr().out
        assert "✓" in output


class TestCmdRaw:
    """Verify raw subcommand output."""

    def test_raw_output_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_raw

        client = AsyncMock()
        client._request.return_value = '["test", "data"]'
        args = _mock_args(raw_endpoint="user-settings.data")
        _run(_cmd_raw(client, args))
        output = capsys.readouterr().out
        assert "RAW DECODED RESPONSE" in output

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from custom_components.rouvy.api_client.__main__ import _cmd_raw

        client = AsyncMock()
        client._request.return_value = '["test", "data"]'
        args = _mock_args(raw_endpoint="test.data", json_output=True)
        _run(_cmd_raw(client, args))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)


# ===================================================================
# main() entry point
# ===================================================================


class TestMain:
    """Verify main() parses args and dispatches to _async_main.

    We patch _async_main to avoid asyncio.run() conflicts with the
    HA test framework's custom event loop policy.
    """

    def test_main_dispatches_to_async_main(self) -> None:
        """Verify main() calls asyncio.run(_async_main(args))."""
        from custom_components.rouvy.api_client.__main__ import main

        mock_async_main = AsyncMock()
        with (
            patch("sys.argv", ["rouvy", "profile"]),
            patch(f"{_CLI_MOD}._async_main", mock_async_main),
            patch(f"{_CLI_MOD}.asyncio.run") as mock_run,
        ):
            main()
        # asyncio.run was called with a coroutine
        mock_run.assert_called_once()

    def test_main_default_uses_profile_handler(self) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        with (
            patch("sys.argv", ["rouvy"]),
            patch(f"{_CLI_MOD}.asyncio.run") as mock_run,
        ):
            main()
        mock_run.assert_called_once()

    def test_main_value_error_exits_1(self) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        with (
            patch("sys.argv", ["rouvy"]),
            patch(
                f"{_CLI_MOD}.asyncio.run",
                side_effect=ValueError("bad"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1

    def test_main_json_error_on_exception(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        with (
            patch("sys.argv", ["rouvy", "--json"]),
            patch(
                f"{_CLI_MOD}.asyncio.run",
                side_effect=RuntimeError("fail"),
            ),
            pytest.raises(SystemExit),
        ):
            main()
        stderr = capsys.readouterr().err
        data = json.loads(stderr)
        assert "error" in data


class TestAsyncMain:
    """Verify _async_main creates client and dispatches handler."""

    def test_dispatches_handler(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _async_main

        mock_handler = AsyncMock()
        args = _mock_args(handler=mock_handler)

        with patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b", "pw")):
            _run(_async_main(args))
        mock_handler.assert_called_once()
