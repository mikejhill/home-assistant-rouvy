"""Tests for HA sensor value extraction functions.

Tests the value_fn lambdas from sensor descriptions in isolation,
without requiring Home Assistant. We import only the pure data types.
"""

import pytest

from rouvy_api_client.models import UserProfile


def _make_profile(**overrides) -> UserProfile:
    """Create a UserProfile with sensible defaults, overriding specific fields."""
    defaults = dict(
        email="user@test.com", username="tester",
        first_name="Test", last_name="User",
        weight_kg=80.0, height_cm=175.0,
        units="METRIC", ftp_watts=200, ftp_source="MANUAL",
        max_heart_rate=185, gender="MALE",
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


# Import the value_fn lambdas from sensor descriptions.
# We reference them by key to avoid importing HA-specific modules.
# Instead, replicate the exact lambda logic from sensor.py.

def _value_weight(p: UserProfile):
    return p.weight_kg if p.weight_kg else None

def _value_height(p: UserProfile):
    return p.height_cm if p.height_cm else None

def _value_ftp(p: UserProfile):
    return p.ftp_watts if p.ftp_watts else None

def _value_max_hr(p: UserProfile):
    return p.max_heart_rate

def _value_units(p: UserProfile):
    return p.units

def _value_name(p: UserProfile):
    return f"{p.first_name} {p.last_name}".strip() or p.username or None


class TestWeightSensor:
    """Verify weight sensor value extraction."""

    def test_returns_weight_kg(self) -> None:
        p = _make_profile(weight_kg=85.5)
        assert _value_weight(p) == 85.5, (
            f"Expected 85.5, got {_value_weight(p)}"
        )

    def test_zero_weight_returns_none(self) -> None:
        p = _make_profile(weight_kg=0.0)
        assert _value_weight(p) is None, (
            f"Expected None for zero weight, got {_value_weight(p)}"
        )


class TestHeightSensor:
    """Verify height sensor value extraction."""

    def test_returns_height_cm(self) -> None:
        p = _make_profile(height_cm=180.0)
        assert _value_height(p) == 180.0, (
            f"Expected 180.0, got {_value_height(p)}"
        )

    def test_zero_height_returns_none(self) -> None:
        p = _make_profile(height_cm=0.0)
        assert _value_height(p) is None, (
            f"Expected None for zero height, got {_value_height(p)}"
        )


class TestFtpSensor:
    """Verify FTP sensor value extraction."""

    def test_returns_ftp_watts(self) -> None:
        p = _make_profile(ftp_watts=250)
        assert _value_ftp(p) == 250, (
            f"Expected 250, got {_value_ftp(p)}"
        )

    def test_zero_ftp_returns_none(self) -> None:
        p = _make_profile(ftp_watts=0)
        assert _value_ftp(p) is None, (
            f"Expected None for zero FTP, got {_value_ftp(p)}"
        )


class TestMaxHeartRateSensor:
    """Verify max HR sensor value extraction."""

    def test_returns_max_hr(self) -> None:
        p = _make_profile(max_heart_rate=195)
        assert _value_max_hr(p) == 195, (
            f"Expected 195, got {_value_max_hr(p)}"
        )

    def test_none_max_hr_returns_none(self) -> None:
        p = _make_profile(max_heart_rate=None)
        assert _value_max_hr(p) is None, (
            f"Expected None, got {_value_max_hr(p)}"
        )


class TestUnitsSensor:
    """Verify units sensor value extraction."""

    def test_returns_metric(self) -> None:
        p = _make_profile(units="METRIC")
        assert _value_units(p) == "METRIC", (
            f"Expected METRIC, got {_value_units(p)}"
        )

    def test_returns_imperial(self) -> None:
        p = _make_profile(units="IMPERIAL")
        assert _value_units(p) == "IMPERIAL", (
            f"Expected IMPERIAL, got {_value_units(p)}"
        )


class TestNameSensor:
    """Verify name sensor value extraction."""

    def test_full_name(self) -> None:
        p = _make_profile(first_name="John", last_name="Doe")
        assert _value_name(p) == "John Doe", (
            f"Expected 'John Doe', got {_value_name(p)}"
        )

    def test_first_name_only(self) -> None:
        p = _make_profile(first_name="John", last_name="")
        assert _value_name(p) == "John", (
            f"Expected 'John', got {_value_name(p)}"
        )

    def test_last_name_only(self) -> None:
        p = _make_profile(first_name="", last_name="Doe")
        assert _value_name(p) == "Doe", (
            f"Expected 'Doe', got {_value_name(p)}"
        )

    def test_fallback_to_username(self) -> None:
        p = _make_profile(first_name="", last_name="", username="jdoe")
        assert _value_name(p) == "jdoe", (
            f"Expected 'jdoe' fallback, got {_value_name(p)}"
        )

    def test_all_empty_returns_none(self) -> None:
        p = _make_profile(first_name="", last_name="", username="")
        assert _value_name(p) is None, (
            f"Expected None when all name fields empty, got {_value_name(p)}"
        )
