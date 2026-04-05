"""Tests for HA sensor value extraction functions.

Tests the value_fn lambdas from sensor descriptions in isolation,
without requiring Home Assistant. We import only the pure data types.
"""

from __future__ import annotations

from custom_components.rouvy.api_client.models import (
    ActivityTypeStats,
    Challenge,
    RouvyCoordinatorData,
    UserProfile,
    WeeklyActivityStats,
)
from custom_components.rouvy.sensor import _current_week_ride_stats


def _make_profile(**overrides) -> UserProfile:
    """Create a UserProfile with sensible defaults, overriding specific fields."""
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


def _make_data(**overrides) -> RouvyCoordinatorData:
    """Create coordinator data wrapping a UserProfile."""
    return RouvyCoordinatorData(profile=_make_profile(**overrides))


# Replicate the exact lambda logic from sensor.py value_fn definitions.


def _value_weight(d: RouvyCoordinatorData):
    return d.profile.weight_kg if d.profile.weight_kg else None


def _value_height(d: RouvyCoordinatorData):
    return d.profile.height_cm if d.profile.height_cm else None


def _value_ftp(d: RouvyCoordinatorData):
    return d.profile.ftp_watts if d.profile.ftp_watts else None


def _value_max_hr(d: RouvyCoordinatorData):
    return d.profile.max_heart_rate


def _value_units(d: RouvyCoordinatorData):
    return d.profile.units


def _value_name(d: RouvyCoordinatorData):
    return f"{d.profile.first_name} {d.profile.last_name}".strip() or d.profile.username or None


class TestWeightSensor:
    """Verify weight sensor value extraction."""

    def test_returns_weight_kg(self) -> None:
        d = _make_data(weight_kg=85.5)
        assert _value_weight(d) == 85.5, f"Expected 85.5, got {_value_weight(d)}"

    def test_zero_weight_returns_none(self) -> None:
        d = _make_data(weight_kg=0.0)
        assert _value_weight(d) is None, f"Expected None for zero weight, got {_value_weight(d)}"


class TestHeightSensor:
    """Verify height sensor value extraction."""

    def test_returns_height_cm(self) -> None:
        d = _make_data(height_cm=180.0)
        assert _value_height(d) == 180.0, f"Expected 180.0, got {_value_height(d)}"

    def test_zero_height_returns_none(self) -> None:
        d = _make_data(height_cm=0.0)
        assert _value_height(d) is None, f"Expected None for zero height, got {_value_height(d)}"


class TestFtpSensor:
    """Verify FTP sensor value extraction."""

    def test_returns_ftp_watts(self) -> None:
        d = _make_data(ftp_watts=250)
        assert _value_ftp(d) == 250, f"Expected 250, got {_value_ftp(d)}"

    def test_zero_ftp_returns_none(self) -> None:
        d = _make_data(ftp_watts=0)
        assert _value_ftp(d) is None, f"Expected None for zero FTP, got {_value_ftp(d)}"


class TestMaxHeartRateSensor:
    """Verify max HR sensor value extraction."""

    def test_returns_max_hr(self) -> None:
        d = _make_data(max_heart_rate=195)
        assert _value_max_hr(d) == 195, f"Expected 195, got {_value_max_hr(d)}"

    def test_none_max_hr_returns_none(self) -> None:
        d = _make_data(max_heart_rate=None)
        assert _value_max_hr(d) is None, f"Expected None, got {_value_max_hr(d)}"


class TestUnitsSensor:
    """Verify units sensor value extraction."""

    def test_returns_metric(self) -> None:
        d = _make_data(units="METRIC")
        assert _value_units(d) == "METRIC", f"Expected METRIC, got {_value_units(d)}"

    def test_returns_imperial(self) -> None:
        d = _make_data(units="IMPERIAL")
        assert _value_units(d) == "IMPERIAL", f"Expected IMPERIAL, got {_value_units(d)}"


class TestNameSensor:
    """Verify name sensor value extraction."""

    def test_full_name(self) -> None:
        d = _make_data(first_name="John", last_name="Doe")
        assert _value_name(d) == "John Doe", f"Expected 'John Doe', got {_value_name(d)}"

    def test_first_name_only(self) -> None:
        d = _make_data(first_name="John", last_name="")
        assert _value_name(d) == "John", f"Expected 'John', got {_value_name(d)}"

    def test_last_name_only(self) -> None:
        d = _make_data(first_name="", last_name="Doe")
        assert _value_name(d) == "Doe", f"Expected 'Doe', got {_value_name(d)}"

    def test_fallback_to_username(self) -> None:
        d = _make_data(first_name="", last_name="", username="jdoe")
        assert _value_name(d) == "jdoe", f"Expected 'jdoe' fallback, got {_value_name(d)}"

    def test_all_empty_returns_none(self) -> None:
        d = _make_data(first_name="", last_name="", username="")
        assert _value_name(d) is None, (
            f"Expected None when all name fields empty, got {_value_name(d)}"
        )


# ===================================================================
# Weekly activity stats sensor helpers
# ===================================================================


def _make_week_stats(**ride_overrides: float | int) -> WeeklyActivityStats:
    """Create a WeeklyActivityStats with configurable ride stats."""
    ride_defaults: dict[str, float | int] = dict(
        distance_m=45000.0,
        elevation_m=350.0,
        calories=800.5,
        moving_time_seconds=5400,
        intensity_factor=0.72,
        training_score=65.3,
        activity_count=3,
    )
    ride_defaults.update(ride_overrides)
    return WeeklyActivityStats(
        week_start="Mar 30, 2026",
        week_end="Apr 5, 2026",
        ride=ActivityTypeStats(**ride_defaults),
    )


def _make_data_with_stats(**ride_overrides: float | int) -> RouvyCoordinatorData:
    """Create coordinator data with activity stats."""
    return RouvyCoordinatorData(
        profile=_make_profile(),
        activity_stats=[_make_week_stats(**ride_overrides)],
    )


class TestCurrentWeekRideStats:
    """Verify _current_week_ride_stats helper."""

    def test_returns_ride_stats_when_present(self) -> None:
        d = _make_data_with_stats()
        stats = _current_week_ride_stats(d)
        assert stats is not None
        assert stats.distance_m == 45000.0

    def test_returns_none_when_no_stats(self) -> None:
        d = RouvyCoordinatorData(profile=_make_profile())
        assert _current_week_ride_stats(d) is None

    def test_returns_none_when_empty_stats(self) -> None:
        d = RouvyCoordinatorData(profile=_make_profile(), activity_stats=[])
        assert _current_week_ride_stats(d) is None


class TestWeeklyDistanceSensor:
    """Verify weekly distance sensor value extraction."""

    def test_returns_km(self) -> None:
        d = _make_data_with_stats(distance_m=45000.0)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_distance")
        assert desc.value_fn(d) == 45.0

    def test_returns_none_when_no_stats(self) -> None:
        d = RouvyCoordinatorData(profile=_make_profile())
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_distance")
        assert desc.value_fn(d) is None


class TestWeeklyElevationSensor:
    """Verify weekly elevation sensor value extraction."""

    def test_returns_meters(self) -> None:
        d = _make_data_with_stats(elevation_m=350.7)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_elevation")
        assert desc.value_fn(d) == 351


class TestWeeklyCaloriesSensor:
    """Verify weekly calories sensor value extraction."""

    def test_returns_kcal(self) -> None:
        d = _make_data_with_stats(calories=800.7)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_calories")
        assert desc.value_fn(d) == 801


class TestWeeklyRideTimeSensor:
    """Verify weekly ride time sensor value extraction."""

    def test_returns_minutes(self) -> None:
        d = _make_data_with_stats(moving_time_seconds=5400)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_ride_time")
        assert desc.value_fn(d) == 90


class TestWeeklyRideCountSensor:
    """Verify weekly ride count sensor value extraction."""

    def test_returns_count(self) -> None:
        d = _make_data_with_stats(activity_count=3)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_ride_count")
        assert desc.value_fn(d) == 3


class TestWeeklyTrainingScoreSensor:
    """Verify weekly training score sensor value extraction."""

    def test_returns_rounded_score(self) -> None:
        d = _make_data_with_stats(training_score=65.3)
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "weekly_training_score")
        assert desc.value_fn(d) == 65


# ===================================================================
# Challenge sensor helpers
# ===================================================================


def _make_challenge(**overrides: object) -> Challenge:
    """Create a Challenge with sensible defaults, overriding specific fields."""
    defaults = dict(
        id="test-challenge",
        user_status="joined",
        state="active",
        registered_count=100,
        registered=True,
        title="Test Challenge",
        logo="",
        experience=500,
        coins=100,
        start_date_time="2026-03-01T00:00:00Z",
        end_date_time="2026-04-01T00:00:00Z",
        is_past=False,
        is_upcoming=False,
        is_done=False,
        segments=[],
    )
    defaults.update(overrides)
    return Challenge(**defaults)


def _make_data_with_challenges(
    *challenges_list: Challenge,
) -> RouvyCoordinatorData:
    return RouvyCoordinatorData(
        profile=_make_profile(),
        challenges=list(challenges_list),
    )


class TestChallengeCounts:
    """Verify _challenge_counts helper and challenge sensor value_fns."""

    def test_active_count(self) -> None:
        from custom_components.rouvy.sensor import _challenge_counts

        d = _make_data_with_challenges(
            _make_challenge(id="c1", registered=True, is_done=False),
            _make_challenge(id="c2", registered=True, is_done=True),
            _make_challenge(id="c3", registered=False, is_done=False),
        )
        counts = _challenge_counts(d)
        assert counts is not None
        assert counts[0] == 1  # active
        assert counts[1] == 1  # completed

    def test_no_challenges_returns_none(self) -> None:
        from custom_components.rouvy.sensor import _challenge_counts

        d = RouvyCoordinatorData(profile=_make_profile())
        assert _challenge_counts(d) is None

    def test_empty_challenges_returns_none(self) -> None:
        from custom_components.rouvy.sensor import _challenge_counts

        d = RouvyCoordinatorData(profile=_make_profile(), challenges=[])
        assert _challenge_counts(d) is None


class TestActiveChallengesSensor:
    """Verify active_challenges sensor value extraction."""

    def test_returns_active_count(self) -> None:
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        d = _make_data_with_challenges(
            _make_challenge(id="c1", registered=True, is_done=False),
            _make_challenge(id="c2", registered=True, is_done=False),
            _make_challenge(id="c3", registered=True, is_done=True),
        )
        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "active_challenges")
        assert desc.value_fn(d) == 2

    def test_returns_none_when_no_challenges(self) -> None:
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        d = RouvyCoordinatorData(profile=_make_profile())
        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "active_challenges")
        assert desc.value_fn(d) is None


class TestCompletedChallengesSensor:
    """Verify completed_challenges sensor value extraction."""

    def test_returns_completed_count(self) -> None:
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        d = _make_data_with_challenges(
            _make_challenge(id="c1", registered=True, is_done=True),
            _make_challenge(id="c2", registered=True, is_done=True),
            _make_challenge(id="c3", registered=True, is_done=False),
        )
        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "completed_challenges")
        assert desc.value_fn(d) == 2

    def test_returns_none_when_no_challenges(self) -> None:
        from custom_components.rouvy.sensor import SENSOR_DESCRIPTIONS

        d = RouvyCoordinatorData(profile=_make_profile())
        desc = next(s for s in SENSOR_DESCRIPTIONS if s.key == "completed_challenges")
        assert desc.value_fn(d) is None
