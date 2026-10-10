"""Typed settings produced by the command-line parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from rouvy_api.client import ProfileUpdate
from rouvy_api.models import AccountPrivacy, UnitSystem, ZoneType

READ_COMMANDS: Final = (
    "login-check",
    "profile",
    "zones",
    "apps",
    "overview",
    "activities",
    "activity-stats",
    "challenges",
    "routes",
    "events",
    "achievements",
    "trophies",
    "raw",
)
WRITE_COMMANDS: Final = (
    "set-weight",
    "set-height",
    "set-units",
    "set-ftp",
    "set-max-hr",
    "set-zones",
    "set-timezone",
    "set-privacy",
    "set-profile",
    "register-challenge",
    "register-event",
    "unregister-event",
)


@dataclass(frozen=True, slots=True)
class GlobalSettings:
    """Options that apply to every command."""

    json_output: bool = False
    log_level: str = "WARNING"
    env_file: Path | None = None
    base_url: str | None = None
    timeout_s: float = 30.0
    email: str | None = None


@dataclass(frozen=True, slots=True)
class CommandArgs:
    """Arguments of the selected command; only the ones it uses are set."""

    number: float | None = None
    text: str | None = None
    year: int | None = None
    month: int | None = None
    favorites_only: bool = False
    estimated: bool = False
    units: UnitSystem | None = None
    privacy: AccountPrivacy | None = None
    zone_type: ZoneType | None = None
    zones: tuple[int, ...] = ()
    profile: ProfileUpdate = field(default_factory=ProfileUpdate)


@dataclass(frozen=True, slots=True)
class RunSettings:
    """Everything needed to run one CLI invocation."""

    command: str
    options: GlobalSettings
    args: CommandArgs

    @property
    def is_write(self) -> bool:
        """Return True for commands that change account data."""
        return self.command in WRITE_COMMANDS
