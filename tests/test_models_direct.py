"""Tests for data model dataclasses via direct instantiation.

These tests do NOT depend on sample files; they verify dataclass
construction, defaults, immutability, and field types.
"""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.rouvy.api_client.models import (
    Activity,
    ActivitySummary,
    ConnectedApp,
    TrainingZones,
    UserProfile,
)


class TestUserProfileDataclass:
    """Verify UserProfile dataclass construction and properties."""

    def test_all_defaults(self) -> None:
        profile = UserProfile(
            email="user@test.com",
            username="tester",
            first_name="Test",
            last_name="User",
            weight_kg=80.0,
            height_cm=175.0,
            units="METRIC",
            ftp_watts=200,
            ftp_source="MANUAL",
        )
        assert profile.email == "user@test.com", (
            f"Expected email user@test.com, got {profile.email}"
        )
        assert profile.max_heart_rate is None, (
            f"Expected None default for max_heart_rate, got {profile.max_heart_rate}"
        )
        assert profile.gender is None, f"Expected None default for gender, got {profile.gender}"
        assert profile.birth_date is None, (
            f"Expected None default for birth_date, got {profile.birth_date}"
        )
        assert profile.country is None, f"Expected None default for country, got {profile.country}"
        assert profile.timezone is None, (
            f"Expected None default for timezone, got {profile.timezone}"
        )
        assert profile.account_privacy is None, (
            f"Expected None default for account_privacy, got {profile.account_privacy}"
        )
        assert profile.user_id is None, f"Expected None default for user_id, got {profile.user_id}"

    def test_with_all_optional_fields(self) -> None:
        profile = UserProfile(
            email="full@test.com",
            username="full",
            first_name="Full",
            last_name="User",
            weight_kg=90.0,
            height_cm=185.0,
            units="IMPERIAL",
            ftp_watts=300,
            ftp_source="ESTIMATED",
            max_heart_rate=195,
            gender="MALE",
            birth_date=date(1990, 6, 15),
            country="GB",
            timezone="Europe/London",
            account_privacy="PRIVATE",
            user_id="uid-999",
        )
        assert profile.max_heart_rate == 195, (
            f"Expected max_heart_rate 195, got {profile.max_heart_rate}"
        )
        assert profile.gender == "MALE", f"Expected gender MALE, got {profile.gender}"
        assert profile.birth_date == date(1990, 6, 15), (
            f"Expected birth date 1990-06-15, got {profile.birth_date}"
        )
        assert profile.country == "GB", f"Expected country GB, got {profile.country}"

    def test_frozen_immutable(self) -> None:
        profile = UserProfile(
            email="e",
            username="u",
            first_name="f",
            last_name="l",
            weight_kg=0,
            height_cm=0,
            units="METRIC",
            ftp_watts=0,
            ftp_source="",
        )
        with pytest.raises(AttributeError, match="cannot assign"):
            profile.email = "changed"  # type: ignore[misc]

    def test_zero_weight_and_height(self) -> None:
        profile = UserProfile(
            email="",
            username="",
            first_name="",
            last_name="",
            weight_kg=0.0,
            height_cm=0.0,
            units="METRIC",
            ftp_watts=0,
            ftp_source="",
        )
        assert profile.weight_kg == 0.0, f"Expected zero weight, got {profile.weight_kg}"
        assert profile.height_cm == 0.0, f"Expected zero height, got {profile.height_cm}"


class TestTrainingZonesDataclass:
    """Verify TrainingZones dataclass construction and properties."""

    def test_defaults_empty_lists(self) -> None:
        zones = TrainingZones(ftp_watts=200, max_heart_rate=190)
        assert zones.power_zone_values == [], (
            f"Expected empty power_zone_values, got {zones.power_zone_values}"
        )
        assert zones.power_zone_defaults == [], (
            f"Expected empty power_zone_defaults, got {zones.power_zone_defaults}"
        )
        assert zones.hr_zone_values == [], (
            f"Expected empty hr_zone_values, got {zones.hr_zone_values}"
        )
        assert zones.hr_zone_defaults == [], (
            f"Expected empty hr_zone_defaults, got {zones.hr_zone_defaults}"
        )

    def test_with_zone_values(self) -> None:
        zones = TrainingZones(
            ftp_watts=250,
            max_heart_rate=195,
            power_zone_values=[55, 75, 90, 105, 120, 150],
            hr_zone_values=[60, 65, 75, 82, 89, 94],
        )
        assert len(zones.power_zone_values) == 6, (
            f"Expected 6 power zones, got {len(zones.power_zone_values)}"
        )

    def test_frozen_immutable(self) -> None:
        zones = TrainingZones(ftp_watts=200, max_heart_rate=190)
        with pytest.raises(AttributeError, match="cannot assign"):
            zones.ftp_watts = 300  # type: ignore[misc]


class TestConnectedAppDataclass:
    """Verify ConnectedApp dataclass construction and properties."""

    def test_required_fields_only(self) -> None:
        app = ConnectedApp(provider_id="strava", name="Strava", status="available")
        assert app.provider_id == "strava", f"Expected provider_id strava, got {app.provider_id}"
        assert app.upload_mode is None, f"Expected None upload_mode, got {app.upload_mode}"
        assert app.permissions == [], f"Expected empty permissions, got {app.permissions}"

    def test_with_all_fields(self) -> None:
        app = ConnectedApp(
            provider_id="garmin",
            name="Garmin Connect",
            status="active",
            upload_mode="auto",
            description="Sync activities",
            logo_path="/logos/garmin.png",
            permissions=["ACTIVITY_EXPORT", "PROFILE_READ"],
        )
        assert app.upload_mode == "auto", f"Expected upload_mode auto, got {app.upload_mode}"
        assert len(app.permissions) == 2, f"Expected 2 permissions, got {len(app.permissions)}"

    def test_frozen_immutable(self) -> None:
        app = ConnectedApp(provider_id="x", name="X", status="x")
        with pytest.raises(AttributeError, match="cannot assign"):
            app.name = "changed"  # type: ignore[misc]


class TestActivityDataclass:
    """Verify Activity dataclass construction and properties."""

    def test_required_fields_only(self) -> None:
        act = Activity(
            activity_id="act-1",
            title="My Ride",
            training_type="ROUTE_TIME_TRIAL",
            distance_m=25000.0,
            moving_time_seconds=3600,
            elevation_m=400.0,
        )
        assert act.activity_id == "act-1", f"Expected activity_id act-1, got {act.activity_id}"
        assert act.start_utc is None, f"Expected None default for start_utc, got {act.start_utc}"
        assert act.intensity_factor is None, (
            f"Expected None default for intensity_factor, got {act.intensity_factor}"
        )

    def test_with_all_optional_fields(self) -> None:
        act = Activity(
            activity_id="act-2",
            title="Evening Spin",
            training_type="WORKOUT",
            distance_m=15000.0,
            moving_time_seconds=1800,
            elevation_m=200.0,
            intensity_factor=0.95,
            start_utc="2024-01-15T08:00:00Z",
        )
        assert act.intensity_factor == 0.95, (
            f"Expected intensity_factor 0.95, got {act.intensity_factor}"
        )
        assert act.start_utc == "2024-01-15T08:00:00Z", (
            f"Expected start_utc string, got {act.start_utc}"
        )

    def test_frozen_immutable(self) -> None:
        act = Activity(
            activity_id="x",
            title="x",
            training_type="",
            distance_m=0,
            moving_time_seconds=0,
            elevation_m=0,
        )
        with pytest.raises(AttributeError, match="cannot assign"):
            act.title = "changed"  # type: ignore[misc]

    def test_zero_distance_and_time(self) -> None:
        act = Activity(
            activity_id="z",
            title="Zero",
            training_type="",
            distance_m=0.0,
            moving_time_seconds=0,
            elevation_m=0.0,
        )
        assert act.distance_m == 0.0, f"Expected 0.0 distance, got {act.distance_m}"
        assert act.moving_time_seconds == 0, (
            f"Expected 0 moving time, got {act.moving_time_seconds}"
        )


class TestActivitySummaryDataclass:
    """Verify ActivitySummary dataclass construction and properties."""

    def test_empty_activities(self) -> None:
        summary = ActivitySummary(recent_activities=[])
        assert summary.recent_activities == [], (
            f"Expected empty list, got {summary.recent_activities}"
        )

    def test_with_activities(self) -> None:
        act = Activity(
            activity_id="a",
            title="t",
            training_type="",
            distance_m=100,
            moving_time_seconds=60,
            elevation_m=0,
        )
        summary = ActivitySummary(recent_activities=[act])
        assert len(summary.recent_activities) == 1, (
            f"Expected 1 activity, got {len(summary.recent_activities)}"
        )
        assert summary.recent_activities[0].activity_id == "a", (
            f"Expected activity_id a, got {summary.recent_activities[0].activity_id}"
        )

    def test_frozen_immutable(self) -> None:
        summary = ActivitySummary(recent_activities=[])
        with pytest.raises(AttributeError, match="cannot assign"):
            summary.recent_activities = []  # type: ignore[misc]
