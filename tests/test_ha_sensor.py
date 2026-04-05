"""Tests for HA sensor value extraction functions.

Tests the value_fn lambdas from sensor descriptions in isolation,
without requiring Home Assistant. We import only the pure data types.
"""

from __future__ import annotations

from custom_components.rouvy.api_client.models import RouvyCoordinatorData, UserProfile


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
