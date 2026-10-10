"""Tests for CLI argument parsing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from rouvy_api.cli.command_line import CommandLine
from rouvy_api.cli.commands import HANDLERS
from rouvy_api.cli.settings import READ_COMMANDS, WRITE_COMMANDS
from rouvy_api.models import AccountPrivacy, UnitSystem, ZoneType


class TestGlobalOptions:
    """Options shared by every command."""

    def test_defaults(self) -> None:
        """Without options, output is text and logging is quiet."""
        settings = CommandLine().parse(["profile"])

        assert settings.command == "profile"
        assert settings.options.json_output is False
        assert settings.options.log_level == "WARNING"
        assert settings.options.timeout_s == 30.0
        assert settings.options.env_file is None
        assert settings.is_write is False

    def test_all_options(self) -> None:
        """Global options are converted to typed values."""
        settings = CommandLine().parse(
            [
                "--json",
                "--log-level",
                "DEBUG",
                "--env-file",
                "creds.env",
                "--base-url",
                "http://127.0.0.1:1",
                "--timeout",
                "5",
                "--email",
                "a@b.c",
                "events",
            ]
        )

        assert settings.options.json_output is True
        assert settings.options.log_level == "DEBUG"
        assert settings.options.env_file == Path("creds.env")
        assert settings.options.base_url == "http://127.0.0.1:1"
        assert settings.options.timeout_s == 5.0
        assert settings.options.email == "a@b.c"

    @pytest.mark.parametrize("argv", [["--timeout", "0", "profile"], ["--log-level", "LOUD", "x"]])
    def test_invalid_global_option(self, argv: list[str]) -> None:
        """Invalid global options are usage errors."""
        with pytest.raises(SystemExit) as excinfo:
            CommandLine().parse(argv)

        assert excinfo.value.code == 2


class TestCommands:
    """Subcommand arguments."""

    def test_every_command_has_a_handler(self) -> None:
        """Every documented command is implemented."""
        assert set(HANDLERS) == set(READ_COMMANDS) | set(WRITE_COMMANDS)

    def test_help_lists_every_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--help shows every command (UX)."""
        with pytest.raises(SystemExit):
            CommandLine().parse(["--help"])

        out = capsys.readouterr().out
        for command in HANDLERS:
            assert command in out

    def test_command_required(self) -> None:
        """Running without a command is a usage error."""
        with pytest.raises(SystemExit) as excinfo:
            CommandLine().parse([])

        assert excinfo.value.code == 2

    def test_activity_stats_defaults_to_this_month(self) -> None:
        """activity-stats defaults to the current year and month."""
        args = CommandLine().parse(["activity-stats"]).args
        today = date.today()  # noqa: DTZ011 - matches the CLI's local-calendar default

        assert (args.year, args.month) == (today.year, today.month)

    def test_activity_stats_explicit(self) -> None:
        """--year and --month are honoured."""
        args = CommandLine().parse(["activity-stats", "--year", "2025", "--month", "3"]).args

        assert (args.year, args.month) == (2025, 3)

    @pytest.mark.parametrize(
        ("argv", "attribute", "expected"),
        [
            (["routes", "--favorites"], "favorites_only", True),
            (["raw", "events.data"], "text", "events.data"),
            (["set-weight", "80.5"], "number", 80.5),
            (["set-height", "180"], "number", 180.0),
            (["set-max-hr", "185"], "number", 185.0),
            (["set-units", "IMPERIAL"], "units", UnitSystem.IMPERIAL),
            (["set-privacy", "PRIVATE"], "privacy", AccountPrivacy.PRIVATE),
            (["set-timezone", "Europe/Prague"], "text", "Europe/Prague"),
            (["register-challenge", "climb"], "text", "climb"),
            (["register-event", "e1"], "text", "e1"),
            (["unregister-event", "e1"], "text", "e1"),
            (["set-ftp", "250"], "number", 250.0),
            (["set-ftp", "--estimated"], "estimated", True),
        ],
    )
    def test_simple_arguments(self, argv: list[str], attribute: str, expected: object) -> None:
        """Positional and flag arguments map to typed fields."""
        args = CommandLine().parse(argv).args

        assert getattr(args, attribute) == expected

    def test_set_zones(self) -> None:
        """Zone boundaries parse into an increasing tuple."""
        args = CommandLine().parse(["set-zones", "heart-rate", "60,65,75,82,89,94"]).args

        assert args.zone_type is ZoneType.HEART_RATE
        assert args.zones == (60, 65, 75, 82, 89, 94)

    def test_set_profile(self) -> None:
        """set-profile builds a ProfileUpdate with only the given fields."""
        settings = CommandLine().parse(
            ["set-profile", "--first-name", "Ada", "--country", "cz", "--birth-date", "1990-05-01"]
        )

        assert settings.is_write is True
        assert settings.args.profile.first_name == "Ada"
        assert settings.args.profile.country == "CZ"
        assert settings.args.profile.birth_date == date(1990, 5, 1)
        assert settings.args.profile.username is None

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["set-weight", "-1"], id="negative-weight"),
            pytest.param(["set-weight", "abc"], id="non-numeric"),
            pytest.param(["set-units", "STONE"], id="bad-units"),
            pytest.param(["set-ftp"], id="ftp-missing"),
            pytest.param(["set-ftp", "250", "--estimated"], id="ftp-both"),
            pytest.param(["set-zones", "power", "55,x"], id="zones-not-int"),
            pytest.param(["set-zones", "power", "75,55"], id="zones-decreasing"),
            pytest.param(["set-zones", "power", "0,55"], id="zones-zero"),
            pytest.param(["set-zones", "power", ","], id="zones-empty"),
            pytest.param(["set-zones", "watts", "55"], id="zones-bad-type"),
            pytest.param(["set-profile"], id="profile-empty"),
            pytest.param(["set-profile", "--birth-date", "May 1"], id="profile-bad-date"),
            pytest.param(["activity-stats", "--month", "13"], id="bad-month"),
            pytest.param(["raw"], id="raw-missing-route"),
        ],
    )
    def test_usage_errors(self, argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
        """Invalid arguments exit with status 2 and an explanation on stderr."""
        with pytest.raises(SystemExit) as excinfo:
            CommandLine().parse(argv)

        assert excinfo.value.code == 2
        assert "error:" in capsys.readouterr().err
