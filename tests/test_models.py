"""Tests for typed model extraction from sample API responses."""

from pathlib import Path

import pytest

from rouvy_api_client.models import (
    Activity,
    ActivitySummary,
    ConnectedApp,
    TrainingZones,
    UserProfile,
)
from rouvy_api_client.parser import (
    extract_activities_model,
    extract_connected_apps_model,
    extract_training_zones_model,
    extract_user_profile,
    extract_user_profile_model,
)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "private-samples"


def _has_samples() -> bool:
    return SAMPLES_DIR.is_dir() and any(SAMPLES_DIR.iterdir())


needs_samples = pytest.mark.skipif(not _has_samples(), reason="Sample data files not present")


# ---------------------------------------------------------------------------
# UserProfile tests
# ---------------------------------------------------------------------------


@needs_samples
class TestUserProfile:
    def _load(self) -> str:
        return (SAMPLES_DIR / "user-settings-data.txt").read_text()

    def test_returns_user_profile_model(self) -> None:
        profile = extract_user_profile_model(self._load())
        assert isinstance(profile, UserProfile)

    def test_basic_fields(self) -> None:
        profile = extract_user_profile_model(self._load())
        assert profile.username == "testuser"
        assert profile.weight_kg == 85.0
        assert profile.height_cm == 178.0
        assert profile.units == "METRIC"
        assert profile.ftp_watts == 165
        assert profile.gender == "MALE"
        assert profile.max_heart_rate == 190
        assert profile.country == "US"
        assert profile.timezone == "America/New_York"

    def test_ftp_source(self) -> None:
        profile = extract_user_profile_model(self._load())
        assert profile.ftp_source == "ESTIMATED"

    def test_account_privacy(self) -> None:
        profile = extract_user_profile_model(self._load())
        assert profile.account_privacy == "PUBLIC"

    def test_birth_date_parsed(self) -> None:
        profile = extract_user_profile_model(self._load())
        if profile.birth_date is not None:
            assert profile.birth_date.year == 1989

    def test_frozen(self) -> None:
        profile = extract_user_profile_model(self._load())
        with pytest.raises(AttributeError):
            profile.weight_kg = 99  # type: ignore[misc]

    def test_backward_compat_dict(self) -> None:
        """extract_user_profile still returns a dict."""
        raw = extract_user_profile(self._load())
        assert isinstance(raw, dict)
        assert raw["username"] == "testuser"
        assert raw["weight_kg"] == 85


# ---------------------------------------------------------------------------
# TrainingZones tests
# ---------------------------------------------------------------------------


@needs_samples
class TestTrainingZones:
    def _load(self) -> str:
        return (SAMPLES_DIR / "user-settings-zones-data.txt").read_text()

    def test_returns_training_zones_model(self) -> None:
        zones = extract_training_zones_model(self._load())
        assert isinstance(zones, TrainingZones)

    def test_ftp_and_max_hr(self) -> None:
        zones = extract_training_zones_model(self._load())
        assert zones.ftp_watts == 165
        assert zones.max_heart_rate == 190

    def test_power_zone_defaults_resolved(self) -> None:
        zones = extract_training_zones_model(self._load())
        assert len(zones.power_zone_defaults) == 6
        assert zones.power_zone_defaults == [55, 75, 90, 105, 120, 150]

    def test_hr_zone_values_resolved(self) -> None:
        zones = extract_training_zones_model(self._load())
        assert len(zones.hr_zone_values) == 6
        # Index 117 is shared with power zones (maps to 75)
        assert zones.hr_zone_values == [60, 65, 75, 82, 89, 94]

    def test_frozen(self) -> None:
        zones = extract_training_zones_model(self._load())
        with pytest.raises(AttributeError):
            zones.ftp_watts = 200  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConnectedApps tests
# ---------------------------------------------------------------------------


@needs_samples
class TestConnectedApps:
    def _load(self) -> str:
        return (SAMPLES_DIR / "user-settings-connected-apps-data.txt").read_text()

    def test_returns_list_of_connected_app(self) -> None:
        apps = extract_connected_apps_model(self._load())
        assert isinstance(apps, list)
        assert all(isinstance(a, ConnectedApp) for a in apps)

    def test_has_active_providers(self) -> None:
        apps = extract_connected_apps_model(self._load())
        active = [a for a in apps if a.status == "active"]
        assert len(active) >= 2
        names = {a.name for a in active}
        assert "Garmin Connect" in names

    def test_garmin_details(self) -> None:
        apps = extract_connected_apps_model(self._load())
        garmin = next(a for a in apps if a.provider_id == "garminconnect")
        assert garmin.status == "active"
        assert garmin.upload_mode == "auto"
        assert "ACTIVITY_EXPORT" in garmin.permissions
        assert garmin.logo_path is not None

    def test_has_available_providers(self) -> None:
        apps = extract_connected_apps_model(self._load())
        assert len(apps) > 5  # Active + available combined

    def test_frozen(self) -> None:
        apps = extract_connected_apps_model(self._load())
        with pytest.raises(AttributeError):
            apps[0].name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Activities tests
# ---------------------------------------------------------------------------


@needs_samples
class TestActivities:
    def _load(self) -> str:
        return (SAMPLES_DIR / "profile-overview-data.txt").read_text()

    def test_returns_activity_summary(self) -> None:
        summary = extract_activities_model(self._load())
        assert isinstance(summary, ActivitySummary)

    def test_has_activities(self) -> None:
        summary = extract_activities_model(self._load())
        assert len(summary.recent_activities) > 0

    def test_activity_fields(self) -> None:
        summary = extract_activities_model(self._load())
        act = summary.recent_activities[0]
        assert isinstance(act, Activity)
        assert act.activity_id != ""
        assert act.title != ""
        assert act.training_type in ("ROUTE_TIME_TRIAL", "WORKOUT", "")
        assert act.distance_m > 0
        assert act.moving_time_seconds > 0

    def test_frozen(self) -> None:
        summary = extract_activities_model(self._load())
        with pytest.raises(AttributeError):
            summary.recent_activities = []  # type: ignore[misc]
