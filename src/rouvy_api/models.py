"""Immutable data models returned by the Rouvy client."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class UnitSystem(StrEnum):
    """Measurement system preferred by the rider."""

    METRIC = "METRIC"
    IMPERIAL = "IMPERIAL"


class FtpSource(StrEnum):
    """How the rider's FTP is determined."""

    MANUAL = "MANUAL"
    ESTIMATED = "ESTIMATED"


class ZoneType(StrEnum):
    """Kinds of training zones."""

    POWER = "power"
    HEART_RATE = "heartRate"


class AccountPrivacy(StrEnum):
    """Visibility of the rider's account."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class JsonExportable:
    """Mixin that converts a dataclass tree into JSON-compatible values."""

    __slots__ = ()

    def as_json(self) -> dict[str, JsonValue]:
        """Return the model as a JSON-compatible dict."""
        result: dict[str, JsonValue] = {}
        for item in dataclasses.fields(self):  # ty: ignore[invalid-argument-type]  # mixin is only used on dataclasses
            result[item.name] = JsonExportable._convert(getattr(self, item.name))
        return result

    @staticmethod
    def _convert(value: object) -> JsonValue:
        """Convert one field value."""
        if isinstance(value, JsonExportable):
            return value.as_json()
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, tuple | list):
            return [JsonExportable._convert(v) for v in value]
        if value is None or isinstance(value, bool | int | float | str):
            return value
        return str(value)


@dataclass(frozen=True, slots=True)
class UserProfile(JsonExportable):
    """Rider profile from the user settings page."""

    user_id: str | None = None
    email: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    country: str | None = None
    timezone: str | None = None
    language: str | None = None
    account_privacy: str | None = None
    units: str = UnitSystem.METRIC
    weight_kg: float | None = None
    height_cm: float | None = None
    ftp_watts: int | None = None
    estimated_ftp_watts: int | None = None
    ftp_source: str | None = None
    max_heart_rate: int | None = None

    @property
    def display_name(self) -> str | None:
        """Return the full name, falling back to the username."""
        full = " ".join(part for part in (self.first_name, self.last_name) if part is not None)
        return full or self.username

    @property
    def effective_ftp_watts(self) -> int | None:
        """Return the FTP Rouvy trains with: manual value, else the estimate."""
        for candidate in (self.ftp_watts, self.estimated_ftp_watts):
            if candidate is not None and candidate > 0:
                return candidate
        return None


@dataclass(frozen=True, slots=True)
class TrainingZones(JsonExportable):
    """Power and heart-rate zone configuration; boundaries are percentages."""

    ftp_watts: int | None = None
    estimated_ftp_watts: int | None = None
    max_heart_rate: int | None = None
    power_zones: tuple[int, ...] = ()
    power_zone_defaults: tuple[int, ...] = ()
    heart_rate_zones: tuple[int, ...] = ()
    heart_rate_zone_defaults: tuple[int, ...] = ()

    def zones_for(self, zone_type: ZoneType) -> tuple[int, ...]:
        """Return the active boundaries for a zone type, falling back to defaults."""
        if zone_type is ZoneType.POWER:
            return self.power_zones or self.power_zone_defaults
        return self.heart_rate_zones or self.heart_rate_zone_defaults


@dataclass(frozen=True, slots=True)
class ConnectedApp(JsonExportable):
    """A third-party service linked to the Rouvy account."""

    provider_id: str
    name: str
    status: str
    upload_mode: str | None = None
    permissions: tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        """Return True when the connection is live."""
        return self.status.lower() == "active"


@dataclass(frozen=True, slots=True)
class Activity(JsonExportable):
    """One recorded ride or workout."""

    activity_id: str
    title: str | None = None
    started_at: datetime | None = None
    training_type: str | None = None
    distance_m: float = 0.0
    elevation_m: float = 0.0
    moving_time_s: int = 0
    calories_kcal: float | None = None
    training_score: float | None = None
    intensity_factor: float | None = None


@dataclass(frozen=True, slots=True)
class PeriodTotals(JsonExportable):
    """Duration, distance, and ascent totals for a period."""

    duration_s: float = 0.0
    distance_m: float = 0.0
    ascent_m: float = 0.0


@dataclass(frozen=True, slots=True)
class CareerProgress(JsonExportable):
    """Experience points and the career level they correspond to."""

    experience_points: int = 0
    level: int = 0


@dataclass(frozen=True, slots=True)
class FriendsSummary(JsonExportable):
    """Friend counts."""

    total: int = 0
    online: int = 0


@dataclass(frozen=True, slots=True)
class ProfileOverview(JsonExportable):
    """Everything on the rider's profile overview page."""

    recent_activities: tuple[Activity, ...] = ()
    year_totals: PeriodTotals | None = None
    month_totals: PeriodTotals | None = None
    career: CareerProgress | None = None
    friends: FriendsSummary | None = None


@dataclass(frozen=True, slots=True)
class ActivityTypeTotals(JsonExportable):
    """Totals for one activity type within a week."""

    distance_m: float = 0.0
    elevation_m: float = 0.0
    calories_kcal: float = 0.0
    moving_time_s: int = 0
    training_score: float = 0.0
    activity_count: int = 0


@dataclass(frozen=True, slots=True)
class WeeklyActivityStats(JsonExportable):
    """Weekly totals per activity type."""

    week_start: date | None = None
    week_end: date | None = None
    ride: ActivityTypeTotals = field(default_factory=ActivityTypeTotals)
    workout: ActivityTypeTotals = field(default_factory=ActivityTypeTotals)
    event: ActivityTypeTotals = field(default_factory=ActivityTypeTotals)
    outdoor: ActivityTypeTotals = field(default_factory=ActivityTypeTotals)

    def contains(self, day: date) -> bool:
        """Return True when the day falls inside this week."""
        if self.week_start is None or self.week_end is None:
            return False
        return self.week_start <= day <= self.week_end


@dataclass(frozen=True, slots=True)
class Challenge(JsonExportable):
    """A Rouvy challenge."""

    challenge_id: str
    title: str | None = None
    state: str | None = None
    user_status: str | None = None
    registered: bool = False
    is_done: bool = False
    is_past: bool = False
    is_upcoming: bool = False
    registered_count: int = 0
    experience: int = 0
    coins: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """Return True when the rider is registered and the challenge is still open."""
        return self.registered and not self.is_done and not self.is_past


@dataclass(frozen=True, slots=True)
class Route(JsonExportable):
    """A Rouvy route."""

    route_id: int
    name: str | None = None
    distance_m: float = 0.0
    elevation_m: float = 0.0
    estimated_time_s: int = 0
    rating: float | None = None
    country_code: str | None = None
    favorite: bool = False
    online_count: int = 0


@dataclass(frozen=True, slots=True)
class Event(JsonExportable):
    """A scheduled group ride or race."""

    event_id: str
    title: str | None = None
    event_type: str | None = None
    starts_at: datetime | None = None
    registrations: int = 0
    registered: bool = False
    official: bool = False
    coins: int = 0
    experience: int = 0


@dataclass(frozen=True, slots=True)
class AchievementsSummary(JsonExportable):
    """Achievement progress counts."""

    total: int = 0
    earned: int = 0
    coins_earned: int = 0
    experience_earned: int = 0


@dataclass(frozen=True, slots=True)
class TrophiesSummary(JsonExportable):
    """Trophy counts."""

    total: int = 0
