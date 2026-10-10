"""Argument parsing for the rouvy-api command-line interface."""

from __future__ import annotations

import argparse
import itertools
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Final, NoReturn

from rouvy_api.cli.settings import CommandArgs, GlobalSettings, RunSettings
from rouvy_api.client import ProfileUpdate
from rouvy_api.models import AccountPrivacy, UnitSystem, ZoneType

PROG: Final = "rouvy-api"
DESCRIPTION: Final = (
    "Read and update your Rouvy account. Credentials come from ROUVY_EMAIL and "
    "ROUVY_PASSWORD (environment or .env file)."
)
_ZONE_TYPES: Final = {"power": ZoneType.POWER, "heart-rate": ZoneType.HEART_RATE}
_LOG_LEVELS: Final = ("DEBUG", "INFO", "WARNING", "ERROR")
_TEXT_COMMANDS: Final = frozenset(
    {"raw", "set-timezone", "register-challenge", "register-event", "unregister-event"}
)
_NUMBER_COMMANDS: Final = frozenset({"set-weight", "set-height", "set-max-hr"})


class CommandLine:
    """Build the argparse parser and convert its result into RunSettings."""

    def __init__(self) -> None:
        self._parser = self._build_parser()

    def parse(self, argv: Sequence[str] | None = None) -> RunSettings:
        """Parse arguments; usage errors exit with status 2."""
        namespace = self._parser.parse_args(argv)
        options = GlobalSettings(
            json_output=bool(namespace.json),
            log_level=str(namespace.log_level),
            env_file=Path(namespace.env_file) if namespace.env_file else None,
            base_url=str(namespace.base_url) if namespace.base_url else None,
            timeout_s=self._positive(float(namespace.timeout), "--timeout"),
            email=str(namespace.email) if namespace.email else None,
        )
        command = str(namespace.command)
        return RunSettings(command=command, options=options, args=self._args(command, namespace))

    # Conversion

    def _args(self, command: str, ns: argparse.Namespace) -> CommandArgs:
        """Convert the subcommand's namespace into typed arguments."""
        converters: dict[str, Callable[[argparse.Namespace], CommandArgs]] = {
            "activity-stats": self._activity_stats,
            "routes": lambda n: CommandArgs(favorites_only=bool(n.favorites)),
            "set-units": lambda n: CommandArgs(units=UnitSystem(str(n.units))),
            "set-privacy": lambda n: CommandArgs(privacy=AccountPrivacy(str(n.privacy))),
            "set-ftp": self._ftp,
            "set-zones": lambda n: CommandArgs(
                zone_type=_ZONE_TYPES[str(n.zone_type)], zones=self._zones(str(n.zones))
            ),
            "set-profile": lambda n: CommandArgs(profile=self._profile(n)),
        }
        if command in _TEXT_COMMANDS:
            return CommandArgs(text=str(ns.value))
        if command in _NUMBER_COMMANDS:
            return CommandArgs(number=self._positive(float(ns.value), command))
        converter = converters.get(command)
        return converter(ns) if converter is not None else CommandArgs()

    def _activity_stats(self, ns: argparse.Namespace) -> CommandArgs:
        """Validate the optional year and month."""
        today = date.today()  # noqa: DTZ011 - the rider's local calendar month is intended
        year = int(ns.year) if ns.year is not None else today.year
        month = int(ns.month) if ns.month is not None else today.month
        if not 1 <= month <= 12:  # noqa: PLR2004
            self._fail(f"--month must be between 1 and 12, got {month}")
        return CommandArgs(year=year, month=month)

    def _ftp(self, ns: argparse.Namespace) -> CommandArgs:
        """Require exactly one of a wattage or --estimated."""
        if ns.estimated and ns.watts is not None:
            self._fail("set-ftp takes either WATTS or --estimated, not both")
        if not ns.estimated and ns.watts is None:
            self._fail("set-ftp needs WATTS or --estimated")
        if ns.estimated:
            return CommandArgs(estimated=True)
        return CommandArgs(number=self._positive(float(ns.watts), "WATTS"))

    def _zones(self, raw: str) -> tuple[int, ...]:
        """Parse ``55,75,90`` into increasing positive integers."""
        try:
            values = tuple(int(part) for part in raw.split(",") if part.strip())
        except ValueError:
            self._fail(f"Zone boundaries must be comma-separated integers, got {raw!r}")
        if not values or any(v <= 0 for v in values):
            self._fail("Zone boundaries must be positive")
        if any(b <= a for a, b in itertools.pairwise(values)):
            self._fail(f"Zone boundaries must increase, got {raw!r}")
        return values

    def _profile(self, ns: argparse.Namespace) -> ProfileUpdate:
        """Build a ProfileUpdate, requiring at least one field."""
        birth_date: date | None = None
        if ns.birth_date is not None:
            try:
                birth_date = date.fromisoformat(str(ns.birth_date))
            except ValueError:
                self._fail(f"--birth-date must be YYYY-MM-DD, got {ns.birth_date!r}")
        update = ProfileUpdate(
            username=ns.username,
            first_name=ns.first_name,
            last_name=ns.last_name,
            country=str(ns.country).upper() if ns.country else None,
            gender=ns.gender,
            birth_date=birth_date,
            language=ns.language,
        )
        if update.is_empty:
            self._fail("set-profile needs at least one field to change")
        return update

    def _positive(self, value: float, name: str) -> float:
        """Reject zero or negative numbers."""
        if value <= 0:
            self._fail(f"{name} must be positive, got {value:g}")
        return value

    def _fail(self, message: str) -> NoReturn:
        """Report a usage error and exit with status 2."""
        self._parser.error(message)

    # Parser definition

    @classmethod
    def _build_parser(cls) -> argparse.ArgumentParser:
        """Define global options and every subcommand."""
        parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION)
        parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
        parser.add_argument(
            "--log-level", choices=_LOG_LEVELS, default="WARNING", help="default: %(default)s"
        )
        parser.add_argument("--env-file", help="credentials file (default: .env if present)")
        parser.add_argument("--base-url", help="portal URL (default: $ROUVY_BASE_URL or Rouvy)")
        parser.add_argument("--timeout", type=float, default=30.0, help="seconds (%(default)s)")
        parser.add_argument("--email", help="override ROUVY_EMAIL")
        commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
        cls._add_reads(commands)
        cls._add_writes(commands)
        return parser

    @staticmethod
    def _add_reads(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Define read-only commands."""
        commands.add_parser("login-check", help="verify the credentials work")
        for name, text in (
            ("profile", "show the rider profile"),
            ("zones", "show FTP, max heart rate, and zones"),
            ("apps", "list connected apps"),
            ("overview", "show totals, career, and friends"),
            ("activities", "list recent activities"),
            ("challenges", "list available challenges"),
            ("events", "list upcoming events"),
            ("achievements", "show achievement progress"),
            ("trophies", "show trophy count"),
        ):
            commands.add_parser(name, help=text)
        stats = commands.add_parser("activity-stats", help="weekly totals for a month")
        stats.add_argument("--year", type=int, help="default: this year")
        stats.add_argument("--month", type=int, help="1-12, default: this month")
        routes = commands.add_parser("routes", help="list routes")
        routes.add_argument("--favorites", action="store_true", help="only favorite routes")
        raw = commands.add_parser("raw", help="print a decoded .data route, e.g. events.data")
        raw.add_argument("value", metavar="ROUTE")

    @staticmethod
    def _add_writes(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Define commands that change account data."""
        for name, metavar, text in (
            ("set-weight", "KG", "set weight in kilograms"),
            ("set-height", "CM", "set height in centimeters"),
            ("set-max-hr", "BPM", "set maximum heart rate"),
        ):
            commands.add_parser(name, help=text).add_argument("value", type=float, metavar=metavar)
        units = commands.add_parser("set-units", help="switch metric/imperial")
        units.add_argument("units", choices=[u.value for u in UnitSystem])
        ftp = commands.add_parser("set-ftp", help="set a manual FTP or use the estimate")
        ftp.add_argument("watts", type=float, nargs="?", metavar="WATTS")
        ftp.add_argument("--estimated", action="store_true", help="let Rouvy estimate FTP")
        zones = commands.add_parser("set-zones", help="replace zone boundaries")
        zones.add_argument("zone_type", choices=list(_ZONE_TYPES))
        zones.add_argument("zones", metavar="BOUNDARIES", help="e.g. 55,75,90,105,120,150")
        privacy = commands.add_parser("set-privacy", help="make the account public or private")
        privacy.add_argument("privacy", choices=[p.value for p in AccountPrivacy])
        for name, metavar, text in (
            ("set-timezone", "TZ", "set the IANA timezone"),
            ("register-challenge", "SLUG", "join a challenge"),
            ("register-event", "EVENT_ID", "join an event"),
            ("unregister-event", "EVENT_ID", "leave an event"),
        ):
            commands.add_parser(name, help=text).add_argument("value", metavar=metavar)
        profile = commands.add_parser("set-profile", help="change profile fields")
        for flag in ("--username", "--first-name", "--last-name", "--country", "--language"):
            profile.add_argument(flag)
        profile.add_argument("--gender", choices=["MALE", "FEMALE"])
        profile.add_argument("--birth-date", metavar="YYYY-MM-DD")
