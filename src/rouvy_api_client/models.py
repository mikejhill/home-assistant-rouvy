"""
Typed data models for Rouvy API responses.

These frozen dataclasses represent the structured data returned by various
Rouvy API endpoints. They are HTTP-library-agnostic and can be used by
both the sync CLI client and the async Home Assistant integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class UserProfile:
    """User profile data from the user-settings endpoint."""

    email: str = ""
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    weight_kg: float = 0.0
    height_cm: float = 0.0
    units: str = "METRIC"
    ftp_watts: int = 0
    ftp_source: str = ""
    max_heart_rate: int | None = None
    gender: str | None = None
    birth_date: date | None = None
    country: str | None = None
    timezone: str | None = None
    account_privacy: str | None = None
    user_id: str | None = None


@dataclass(frozen=True)
class TrainingZones:
    """Training zone configuration from the zones endpoint.

    Zone boundary values are percentages of FTP (power) or max HR (heart rate).
    Each list has N-1 boundaries defining N zones.
    """

    ftp_watts: int = 0
    max_heart_rate: int = 0
    power_zone_values: list[int] = field(default_factory=list)
    power_zone_defaults: list[int] = field(default_factory=list)
    hr_zone_values: list[int] = field(default_factory=list)
    hr_zone_defaults: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ConnectedApp:
    """A third-party app integration."""

    provider_id: str = ""
    name: str = ""
    status: str = ""
    upload_mode: str | None = None
    description: str | None = None
    logo_path: str | None = None
    permissions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Activity:
    """A single Rouvy activity (ride)."""

    activity_id: str = ""
    title: str = ""
    start_utc: str | None = None
    training_type: str = ""
    distance_m: float = 0.0
    elevation_m: float = 0.0
    moving_time_seconds: int = 0
    intensity_factor: float | None = None


@dataclass(frozen=True)
class ActivitySummary:
    """Activity summary from the profile overview endpoint."""

    recent_activities: list[Activity] = field(default_factory=list)
