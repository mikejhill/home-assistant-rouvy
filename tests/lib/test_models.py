"""Tests for model behaviour and JSON export."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from rouvy_api import (
    Challenge,
    ConnectedApp,
    ProfileOverview,
    TrainingZones,
    UserProfile,
    WeeklyActivityStats,
    ZoneType,
)
from rouvy_api.models import Activity, CareerProgress, JsonExportable, UnitSystem


class TestUserProfile:
    """Derived profile values."""

    @pytest.mark.parametrize(
        ("first", "last", "username", "expected"),
        [
            ("Ada", "Lovelace", "ada", "Ada Lovelace"),
            ("Ada", None, "ada", "Ada"),
            (None, None, "ada", "ada"),
            (None, None, None, None),
        ],
    )
    def test_display_name(
        self, first: str | None, last: str | None, username: str | None, expected: str | None
    ) -> None:
        """The display name prefers the full name, then the username."""
        profile = UserProfile(first_name=first, last_name=last, username=username)

        assert profile.display_name == expected

    @pytest.mark.parametrize(
        ("manual", "estimated", "expected"),
        [(250, 165, 250), (0, 165, 165), (None, 165, 165), (0, 0, None), (None, None, None)],
    )
    def test_effective_ftp(
        self, manual: int | None, estimated: int | None, expected: int | None
    ) -> None:
        """Effective FTP is the manual value, else the estimate."""
        profile = UserProfile(ftp_watts=manual, estimated_ftp_watts=estimated)

        assert profile.effective_ftp_watts == expected


class TestSmallModels:
    """Predicates on small models."""

    def test_zones_for_falls_back_to_defaults(self) -> None:
        """Custom zones win; defaults fill in when none are set."""
        zones = TrainingZones(power_zone_defaults=(1, 2), heart_rate_zones=(3, 4))

        assert zones.zones_for(ZoneType.POWER) == (1, 2)
        assert zones.zones_for(ZoneType.HEART_RATE) == (3, 4)

    @pytest.mark.parametrize(
        ("status", "active"), [("active", True), ("ACTIVE", True), ("never_connected", False)]
    )
    def test_app_active(self, status: str, *, active: bool) -> None:
        """Apps are active only with an active status."""
        assert ConnectedApp("p", "P", status).is_active is active

    @pytest.mark.parametrize(
        ("registered", "done", "past", "active"),
        [
            (True, False, False, True),
            (True, True, False, False),
            (True, False, True, False),
            (False, False, False, False),
        ],
    )
    def test_challenge_active(self, registered: bool, done: bool, past: bool, active: bool) -> None:
        """A challenge is active when joined, unfinished, and not past."""
        challenge = Challenge("c", registered=registered, is_done=done, is_past=past)

        assert challenge.is_active is active

    def test_week_contains(self) -> None:
        """A week contains its first and last day only."""
        week = WeeklyActivityStats(week_start=date(2026, 10, 5), week_end=date(2026, 10, 11))

        assert week.contains(date(2026, 10, 5))
        assert week.contains(date(2026, 10, 11))
        assert not week.contains(date(2026, 10, 12))


class TestJsonExport:
    """as_json() produces JSON-compatible data."""

    def test_nested_conversion(self) -> None:
        """Dates, datetimes, tuples, nested models, and enums are converted."""
        overview = ProfileOverview(
            recent_activities=(Activity("a1", started_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC)),),
            career=CareerProgress(experience_points=10, level=1),
        )

        data = overview.as_json()

        assert data["recent_activities"] == [
            {
                "activity_id": "a1",
                "title": None,
                "started_at": "2026-01-02T03:04:00+00:00",
                "training_type": None,
                "distance_m": 0.0,
                "elevation_m": 0.0,
                "moving_time_s": 0,
                "calories_kcal": None,
                "training_score": None,
                "intensity_factor": None,
            }
        ]
        assert data["career"] == {"experience_points": 10, "level": 1}
        assert data["year_totals"] is None

    def test_enum_and_date(self) -> None:
        """Enum values export as plain strings and dates as ISO dates."""
        data = UserProfile(units=UnitSystem.IMPERIAL, birth_date=date(1990, 1, 1)).as_json()

        assert data["units"] == "IMPERIAL"
        assert data["birth_date"] == "1990-01-01"

    def test_unknown_values_are_stringified(self) -> None:
        """Unexpected value types fall back to str()."""
        converted = JsonExportable._convert(object)

        assert isinstance(converted, str)
        assert converted.startswith("<class")
