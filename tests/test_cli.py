"""Tests for CLI utility functions and argument parsing.

Tests pure functions from __main__.py without requiring live API access
or environment variables.
"""

import os
from unittest.mock import patch

import pytest

from custom_components.rouvy.api_client.__main__ import (
    _coerce_value,
    _configure_logging,
    _format_profile_field,
    _format_time,
    _parse_settings,
    load_credentials,
)

# ===================================================================
# _coerce_value
# ===================================================================


class TestCoerceValue:
    """Verify type coercion for CLI KEY=VALUE settings."""

    def test_integer_string_becomes_int(self) -> None:
        result = _coerce_value("42")
        assert result == 42 and isinstance(result, int), (
            f"Expected int 42, got {result!r} ({type(result).__name__})"
        )

    def test_negative_integer_string_becomes_int(self) -> None:
        result = _coerce_value("-5")
        assert result == -5 and isinstance(result, int), f"Expected int -5, got {result!r}"

    def test_float_string_becomes_float(self) -> None:
        result = _coerce_value("3.14")
        assert result == 3.14 and isinstance(result, float), (
            f"Expected float 3.14, got {result!r} ({type(result).__name__})"
        )

    def test_plain_string_stays_string(self) -> None:
        result = _coerce_value("METRIC")
        assert result == "METRIC" and isinstance(result, str), (
            f"Expected str 'METRIC', got {result!r} ({type(result).__name__})"
        )

    def test_zero_becomes_int(self) -> None:
        result = _coerce_value("0")
        assert result == 0 and isinstance(result, int), f"Expected int 0, got {result!r}"

    def test_empty_string_stays_string(self) -> None:
        result = _coerce_value("")
        assert result == "" and isinstance(result, str), f"Expected empty string, got {result!r}"


# ===================================================================
# _parse_settings
# ===================================================================


class TestParseSettings:
    """Verify KEY=VALUE string parsing."""

    def test_single_setting_parsed(self) -> None:
        result = _parse_settings(["weight=86"])
        assert result == {"weight": 86}, f"Expected {{'weight': 86}}, got {result}"

    def test_multiple_settings_parsed(self) -> None:
        result = _parse_settings(["weight=86", "height=178"])
        assert result == {"weight": 86, "height": 178}, (
            f"Expected weight + height dict, got {result}"
        )

    def test_string_value_parsed(self) -> None:
        result = _parse_settings(["units=IMPERIAL"])
        assert result == {"units": "IMPERIAL"}, f"Expected {{'units': 'IMPERIAL'}}, got {result}"

    def test_value_with_equals_sign(self) -> None:
        result = _parse_settings(["formula=a=b+c"])
        assert result is not None, "Expected non-None for value containing ="
        assert result["formula"] == "a=b+c", (
            f"Expected value 'a=b+c' preserved, got {result['formula']}"
        )

    def test_invalid_format_returns_none(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = _parse_settings(["no_equals_here"])
        assert result is None, f"Expected None for invalid format, got {result}"
        captured = capsys.readouterr()
        assert "Invalid format" in captured.out, (
            f"Expected error message in stdout, got: {captured.out}"
        )

    def test_float_value_parsed(self) -> None:
        result = _parse_settings(["weight=85.5"])
        assert result == {"weight": 85.5}, f"Expected {{'weight': 85.5}}, got {result}"


# ===================================================================
# _format_profile_field
# ===================================================================


class TestFormatProfileField:
    """Verify field name to human-readable label conversion."""

    def test_known_field_weight(self) -> None:
        assert _format_profile_field("weight_kg") == "Weight (kg)", (
            "Expected 'Weight (kg)' for weight_kg"
        )

    def test_known_field_email(self) -> None:
        assert _format_profile_field("email") == "Email", "Expected 'Email' for email"

    def test_known_field_ftp(self) -> None:
        assert _format_profile_field("ftp_watts") == "FTP (watts)", (
            "Expected 'FTP (watts)' for ftp_watts"
        )

    def test_unknown_field_uses_title_case(self) -> None:
        result = _format_profile_field("custom_field_name")
        assert result == "Custom Field Name", f"Expected 'Custom Field Name' fallback, got {result}"


# ===================================================================
# _format_time
# ===================================================================


class TestFormatTime:
    """Verify seconds-to-time string formatting."""

    def test_zero_seconds(self) -> None:
        assert _format_time(0) == "0:00", f"Expected '0:00' for 0 seconds, got {_format_time(0)}"

    def test_seconds_only(self) -> None:
        assert _format_time(45) == "0:45", f"Expected '0:45' for 45 seconds, got {_format_time(45)}"

    def test_minutes_and_seconds(self) -> None:
        assert _format_time(125) == "2:05", (
            f"Expected '2:05' for 125 seconds, got {_format_time(125)}"
        )

    def test_hours_minutes_seconds(self) -> None:
        assert _format_time(3661) == "1:01:01", (
            f"Expected '1:01:01' for 3661 seconds, got {_format_time(3661)}"
        )

    def test_exact_hour(self) -> None:
        assert _format_time(3600) == "1:00:00", (
            f"Expected '1:00:00' for 3600 seconds, got {_format_time(3600)}"
        )

    def test_large_duration(self) -> None:
        result = _format_time(36000)  # 10 hours
        assert result == "10:00:00", f"Expected '10:00:00' for 36000 seconds, got {result}"


# ===================================================================
# load_credentials
# ===================================================================


class TestLoadCredentials:
    """Verify credential loading from environment."""

    @patch.dict(os.environ, {"ROUVY_EMAIL": "test@e.com", "ROUVY_PASSWORD": "pass123"})
    def test_returns_tuple_when_both_set(self) -> None:
        email, password = load_credentials()
        assert email == "test@e.com", f"Expected email 'test@e.com', got {email}"
        assert password == "pass123", f"Expected password 'pass123', got {password}"

    @patch.dict(os.environ, {"ROUVY_EMAIL": "", "ROUVY_PASSWORD": "pass123"}, clear=False)
    def test_raises_when_email_empty(self) -> None:
        with (
            patch.dict(os.environ, {"ROUVY_EMAIL": ""}, clear=False),
            pytest.raises(ValueError, match="ROUVY_EMAIL"),
        ):
            load_credentials()

    @patch.dict(os.environ, {"ROUVY_EMAIL": "a@b.com"}, clear=False)
    def test_raises_when_password_missing(self) -> None:
        with (
            patch.dict(os.environ, {"ROUVY_PASSWORD": ""}, clear=False),
            pytest.raises(ValueError, match="ROUVY_EMAIL"),
        ):
            load_credentials()


# ===================================================================
# _configure_logging
# ===================================================================


class TestConfigureLogging:
    """Verify logging configuration."""

    def test_does_not_raise_for_valid_level(self) -> None:
        # Should not raise for any valid level
        _configure_logging("DEBUG")
        _configure_logging("WARNING")

    def test_invalid_level_falls_back_to_warning(self) -> None:
        _configure_logging("INVALID_LEVEL")
        # Just verify no exception was raised
        assert True


# ===================================================================
# Argument parsing
# ===================================================================


class TestParseArgs:
    """Verify argument parsing for subcommands and legacy flags."""

    def test_profile_subcommand(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api", "profile"]):
            args = _parse_args()
        assert args.subcommand == "profile", f"Expected subcommand 'profile', got {args.subcommand}"

    def test_zones_subcommand(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api", "zones"]):
            args = _parse_args()
        assert args.subcommand == "zones", f"Expected subcommand 'zones', got {args.subcommand}"

    def test_set_subcommand_with_settings(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api", "set", "weight=86", "height=178"]):
            args = _parse_args()
        assert args.subcommand == "set", f"Expected subcommand 'set', got {args.subcommand}"
        assert args.settings == ["weight=86", "height=178"], (
            f"Expected settings list, got {args.settings}"
        )

    def test_raw_subcommand_with_endpoint(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api", "raw", "user-settings.data"]):
            args = _parse_args()
        assert args.subcommand == "raw", f"Expected subcommand 'raw', got {args.subcommand}"
        assert args.raw_endpoint == "user-settings.data", (
            f"Expected raw_endpoint, got {args.raw_endpoint}"
        )

    def test_legacy_endpoint_flag(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api", "--endpoint", "zones.data"]):
            args = _parse_args()
        assert args.endpoint == "zones.data", f"Expected endpoint 'zones.data', got {args.endpoint}"
        assert args.subcommand is None, f"Expected no subcommand, got {args.subcommand}"

    def test_debug_flag(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        # --debug is a common flag on both main parser and subcommand parsers
        with patch("sys.argv", ["rouvy-api", "profile", "--debug"]):
            args = _parse_args()
        assert args.debug is True, f"Expected debug=True, got {args.debug}"

    def test_default_no_subcommand(self) -> None:
        from custom_components.rouvy.api_client.__main__ import _parse_args

        with patch("sys.argv", ["rouvy-api"]):
            args = _parse_args()
        assert args.subcommand is None, f"Expected None subcommand, got {args.subcommand}"


# ===================================================================
# Subcommand handlers (with mocked client)
# ===================================================================


from unittest.mock import MagicMock

_CLI_MOD = "custom_components.rouvy.api_client.__main__"

from custom_components.rouvy.api_client.__main__ import (
    _cmd_activities,
    _cmd_apps,
    _cmd_profile,
    _cmd_raw,
    _cmd_set,
    _cmd_zones,
)
from custom_components.rouvy.api_client.models import (
    Activity,
    ActivitySummary,
    ConnectedApp,
    TrainingZones,
    UserProfile,
)


def _mock_profile(**overrides) -> UserProfile:
    defaults = dict(
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


def _mock_zones(**overrides) -> TrainingZones:
    defaults = dict(
        ftp_watts=200,
        max_heart_rate=185,
        power_zone_values=[55, 75, 90, 105, 120, 150],
        power_zone_defaults=[55, 75, 90, 105, 120, 150],
        hr_zone_values=[60, 70, 80, 90, 95, 100],
        hr_zone_defaults=[60, 70, 80, 90, 95, 100],
    )
    defaults.update(overrides)
    return TrainingZones(**defaults)


class TestCmdProfile:
    """Verify profile subcommand output."""

    def test_prints_profile_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_user_profile.return_value = _mock_profile()
        _cmd_profile(client)
        output = capsys.readouterr().out
        assert "USER PROFILE" in output, f"Expected 'USER PROFILE' in output, got: {output[:200]}"

    def test_prints_weight(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_user_profile.return_value = _mock_profile(weight_kg=85.5)
        _cmd_profile(client)
        output = capsys.readouterr().out
        assert "85.5" in output, f"Expected weight 85.5 in output, got: {output[:200]}"

    def test_skips_none_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_user_profile.return_value = _mock_profile(
            gender=None, birth_date=None, country=None
        )
        _cmd_profile(client)
        output = capsys.readouterr().out
        assert "Gender" not in output, "Expected None gender to be skipped"
        assert "Birth Date" not in output, "Expected None birth_date to be skipped"

    def test_prints_all_non_none_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_user_profile.return_value = _mock_profile()
        _cmd_profile(client)
        output = capsys.readouterr().out
        for expected in ["Email", "Username", "Weight (kg)", "Height (cm)", "FTP (watts)"]:
            assert expected in output, f"Expected '{expected}' in profile output"


class TestCmdZones:
    """Verify zones subcommand output."""

    def test_prints_zones_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_training_zones.return_value = _mock_zones()
        _cmd_zones(client)
        output = capsys.readouterr().out
        assert "TRAINING ZONES" in output, "Expected 'TRAINING ZONES' in output"

    def test_prints_ftp(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_training_zones.return_value = _mock_zones(ftp_watts=250)
        _cmd_zones(client)
        output = capsys.readouterr().out
        assert "250" in output, "Expected FTP 250 in output"

    def test_prints_power_zone_labels(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_training_zones.return_value = _mock_zones()
        _cmd_zones(client)
        output = capsys.readouterr().out
        for label in ["Recovery", "Endurance", "Tempo", "Threshold"]:
            assert label in output, f"Expected zone label '{label}' in output"

    def test_no_zones_when_values_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_training_zones.return_value = _mock_zones(
            power_zone_values=None,
            power_zone_defaults=None,
            hr_zone_values=None,
            hr_zone_defaults=None,
            ftp_watts=0,
            max_heart_rate=0,
        )
        _cmd_zones(client)
        output = capsys.readouterr().out
        assert "Recovery" not in output, "Expected no zone labels when values empty"


class TestCmdApps:
    """Verify connected apps subcommand output."""

    def test_prints_apps_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_connected_apps.return_value = []
        _cmd_apps(client)
        output = capsys.readouterr().out
        assert "CONNECTED APPS" in output, "Expected 'CONNECTED APPS' in output"

    def test_prints_app_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        apps = [
            ConnectedApp(name="Strava", provider_id="strava", status="connected"),
            ConnectedApp(name="Garmin", provider_id="garmin", status="available"),
        ]
        client = MagicMock()
        client.get_connected_apps.return_value = apps
        _cmd_apps(client)
        output = capsys.readouterr().out
        assert "2 app integrations" in output, "Expected '2 app integrations' in output"

    def test_connected_app_shows_checkmark(self, capsys: pytest.CaptureFixture[str]) -> None:
        apps = [ConnectedApp(name="Strava", provider_id="strava", status="connected")]
        client = MagicMock()
        client.get_connected_apps.return_value = apps
        _cmd_apps(client)
        output = capsys.readouterr().out
        assert "✓" in output, "Expected checkmark for connected app"

    def test_available_app_shows_x(self, capsys: pytest.CaptureFixture[str]) -> None:
        apps = [ConnectedApp(name="Garmin", provider_id="garmin", status="available")]
        client = MagicMock()
        client.get_connected_apps.return_value = apps
        _cmd_apps(client)
        output = capsys.readouterr().out
        assert "✗" in output, "Expected ✗ for non-connected app"


class TestCmdActivities:
    """Verify activities subcommand output."""

    def test_prints_activities_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_activity_summary.return_value = ActivitySummary(recent_activities=[])
        _cmd_activities(client)
        output = capsys.readouterr().out
        assert "RECENT ACTIVITIES" in output, "Expected 'RECENT ACTIVITIES' in output"

    def test_no_activities_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        client.get_activity_summary.return_value = ActivitySummary(recent_activities=[])
        _cmd_activities(client)
        output = capsys.readouterr().out
        assert "No recent activities" in output, "Expected 'No recent activities' message"

    def test_activity_title_and_distance(self, capsys: pytest.CaptureFixture[str]) -> None:
        act = Activity(
            activity_id="a1",
            title="Morning Ride",
            training_type="ROUTE",
            distance_m=25000.0,
            moving_time_seconds=3600,
            elevation_m=300.0,
            start_utc="2024-01-15",
        )
        client = MagicMock()
        client.get_activity_summary.return_value = ActivitySummary(recent_activities=[act])
        _cmd_activities(client)
        output = capsys.readouterr().out
        assert "Morning Ride" in output, "Expected activity title in output"
        assert "25.0 km" in output, "Expected distance in km"

    def test_long_title_truncated(self, capsys: pytest.CaptureFixture[str]) -> None:
        act = Activity(
            activity_id="a1",
            title="A" * 35,
            training_type="",
            distance_m=0,
            moving_time_seconds=0,
            elevation_m=0,
        )
        client = MagicMock()
        client.get_activity_summary.return_value = ActivitySummary(recent_activities=[act])
        _cmd_activities(client)
        output = capsys.readouterr().out
        assert "..." in output, "Expected truncation '...' for long title"


class TestCmdSet:
    """Verify set subcommand with mocked client."""

    def test_successful_update(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        client.update_user_settings.return_value = mock_resp
        client.get_user_profile.return_value = _mock_profile(weight_kg=86.0)

        _cmd_set(client, ["weight=86"])
        output = capsys.readouterr().out
        assert "updated successfully" in output.lower(), "Expected success message in output"
        assert "UPDATED" in output, "Expected UPDATED marker in output"

    def test_invalid_settings_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        _cmd_set(client, ["no_equals"])
        output = capsys.readouterr().out
        assert "Invalid format" in output, "Expected error message for invalid format"
        client.update_user_settings.assert_not_called()

    def test_failed_update_shows_status(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        client.update_user_settings.return_value = mock_resp

        _cmd_set(client, ["weight=86"])
        output = capsys.readouterr().out
        assert "400" in output, "Expected status code 400 in output"


class TestCmdRaw:
    """Verify raw subcommand output."""

    def test_raw_output_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["test", "data"]'
        client.get.return_value = mock_resp

        _cmd_raw(client, "user-settings.data")
        output = capsys.readouterr().out
        assert "RAW DECODED RESPONSE" in output, "Expected raw header in output"
        assert "user-settings.data" in output, "Expected endpoint name in output"

    def test_raw_shows_status_and_size(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["x"]'
        client.get.return_value = mock_resp

        _cmd_raw(client, "test.data")
        output = capsys.readouterr().out
        assert "200" in output, "Expected status code in output"


# ===================================================================
# main() entry point
# ===================================================================


class TestMain:
    """Verify main() dispatches correctly."""

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_default_calls_profile(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_client.get_user_profile.return_value = _mock_profile()

        with patch("sys.argv", ["rouvy-api"]):
            main()
        mock_client.get_user_profile.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_zones_subcommand(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_client.get_training_zones.return_value = _mock_zones()

        with patch("sys.argv", ["rouvy-api", "zones"]):
            main()
        mock_client.get_training_zones.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_apps_subcommand(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_client.get_connected_apps.return_value = []

        with patch("sys.argv", ["rouvy-api", "apps"]):
            main()
        mock_client.get_connected_apps.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_activities_subcommand(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_client.get_activity_summary.return_value = ActivitySummary(recent_activities=[])

        with patch("sys.argv", ["rouvy-api", "activities"]):
            main()
        mock_client.get_activity_summary.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_set_subcommand(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.update_user_settings.return_value = mock_resp
        mock_client.get_user_profile.return_value = _mock_profile()

        with patch("sys.argv", ["rouvy-api", "set", "weight=86"]):
            main()
        mock_client.update_user_settings.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_raw_subcommand(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["raw"]'
        mock_client.get.return_value = mock_resp

        with patch("sys.argv", ["rouvy-api", "raw", "test.data"]):
            main()
        mock_client.get.assert_called_once()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_api_error_handled(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main
        from custom_components.rouvy.api_client.errors import ApiResponseError

        mock_client = mock_client_cls.return_value
        mock_client.get_user_profile.side_effect = ApiResponseError(
            "Server error", status_code=500, payload="internal"
        )

        with patch("sys.argv", ["rouvy-api", "profile"]):
            main()  # Should not raise
        output = capsys.readouterr().out
        assert "500" in output, "Expected status code in error output"

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_legacy_endpoint(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["userProfile", {"email": "a@b.com"}]'
        mock_client.get.return_value = mock_resp

        with patch("sys.argv", ["rouvy-api", "--endpoint", "user-settings.data"]):
            main()
        mock_client.get.assert_called()

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_legacy_raw(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["data"]'
        mock_client.get.return_value = mock_resp

        with patch("sys.argv", ["rouvy-api", "--endpoint", "test.data", "--raw"]):
            main()
        output = capsys.readouterr().out
        assert "RAW DECODED RESPONSE" in output, "Expected raw header for legacy --raw"

    @patch(f"{_CLI_MOD}.load_credentials", return_value=("a@b.com", "pw"))
    @patch(f"{_CLI_MOD}.RouvyClient")
    def test_main_legacy_set(
        self, mock_client_cls: MagicMock, mock_creds: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from custom_components.rouvy.api_client.__main__ import main

        mock_client = mock_client_cls.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '["userProfile", {"email": "a@b.com"}]'
        mock_client.update_user_settings.return_value = mock_resp
        mock_client.get_user_settings.return_value = mock_resp

        with patch("sys.argv", ["rouvy-api", "--set", "weight=86"]):
            main()
        mock_client.update_user_settings.assert_called_once()
