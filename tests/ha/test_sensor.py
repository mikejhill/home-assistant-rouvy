"""Tests for Rouvy sensor values, metadata, and availability."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from custom_components.rouvy.coordinator import RouvySnapshot
from custom_components.rouvy.rouvy_api import (
    Activity,
    ProfileOverview,
    TrainingZones,
    UserProfile,
    WeeklyActivityStats,
    ZoneType,
)
from custom_components.rouvy.sensor import SENSOR_SECTIONS, SENSORS, SnapshotView
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import FakeRouvy
from tests.support.rouvy_payloads import RouvyPayloads

EXPECTED_STATES = {
    "sensor.rouvy_weight": "85.0",
    "sensor.rouvy_height": "178.0",
    "sensor.rouvy_ftp": "165",
    "sensor.rouvy_max_heart_rate": "190",
    "sensor.rouvy_ftp_source": "estimated",
    "sensor.rouvy_units": "metric",
    "sensor.rouvy_name": "test-rider",
    "sensor.rouvy_weekly_distance": "63.0015",
    "sensor.rouvy_weekly_elevation": "930.0",
    "sensor.rouvy_weekly_calories": "1350.0",
    "sensor.rouvy_weekly_ride_time": "180.0",
    "sensor.rouvy_weekly_activities": "3",
    "sensor.rouvy_weekly_training_score": "165.0",
    "sensor.rouvy_monthly_distance": "8.392651",
    "sensor.rouvy_yearly_distance": "89.431219",
    "sensor.rouvy_yearly_elevation": "722.29",
    "sensor.rouvy_last_activity": "Faistos | Crete",
    "sensor.rouvy_last_activity_distance": "7.908154",
    "sensor.rouvy_last_activity_date": "2026-02-03T00:35:07+00:00",
    "sensor.rouvy_active_challenges": "1",
    "sensor.rouvy_completed_challenges": "1",
    "sensor.rouvy_upcoming_events": "1",
    "sensor.rouvy_next_event": "Saturday Morning Ride",
    "sensor.rouvy_next_event_time": "2026-10-12T08:00:00+00:00",
    "sensor.rouvy_favorite_routes": "2",
    "sensor.rouvy_online_riders_on_favorite_routes": "42",
    "sensor.rouvy_career_level": "5",
    "sensor.rouvy_total_xp": "1067",
    "sensor.rouvy_achievements": "2",
    "sensor.rouvy_trophies": "4",
    "sensor.rouvy_friends": "0",
    "sensor.rouvy_online_friends": "0",
    "sensor.rouvy_power_zones": "55, 75, 90, 105, 120, 150",
    "sensor.rouvy_heart_rate_zones": "60, 65, 75, 82, 89, 94",
    "sensor.rouvy_connected_apps": "17",
    "sensor.rouvy_active_connected_apps": "2",
}
NUMERIC_SENSORS = [e for e, v in EXPECTED_STATES.items() if v.replace(".", "", 1).isdigit()]


class TestSensorValues:
    """Sensor states derived from realistic Rouvy data."""

    @pytest.mark.parametrize(("entity_id", "expected"), EXPECTED_STATES.items())
    async def test_state(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, entity_id: str, expected: str
    ) -> None:
        """Each sensor reports the value parsed from Rouvy."""
        state = hass.states.get(entity_id)

        assert state is not None
        assert state.state == expected

    async def test_attributes(self, hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
        """Sensors with context expose it as attributes."""
        challenges = hass.states.get("sensor.rouvy_active_challenges")
        event = hass.states.get("sensor.rouvy_next_event")
        achievements = hass.states.get("sensor.rouvy_achievements")

        assert challenges is not None
        assert challenges.attributes["challenges"] == "October Climb"
        assert event is not None
        assert event.attributes["event_id"] == "3f1c2b9a-5d7e-4a1b-9c3d-2e4f6a8b0c1d"
        assert achievements is not None
        assert achievements.attributes["available"] == 3


class TestSensorRegistry:
    """Entity registry metadata."""

    async def test_unique_ids_are_stable(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, entity_registry: er.EntityRegistry
    ) -> None:
        """Unique ids keep the v1 format so existing entities survive the upgrade."""
        entries = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)

        assert {e.unique_id for e in entries} == {
            f"{loaded_entry.entry_id}_{d.key}" for d in SENSORS
        }

    async def test_diagnostic_and_disabled_defaults(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, entity_registry: er.EntityRegistry
    ) -> None:
        """Configuration sensors are diagnostic and niche ones start disabled."""
        zones = entity_registry.async_get("sensor.rouvy_power_zones")
        country = entity_registry.async_get("sensor.rouvy_country")

        assert zones is not None
        assert zones.entity_category is EntityCategory.DIAGNOSTIC
        assert country is not None
        assert country.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    async def test_every_section_mapping_names_a_sensor(self) -> None:
        """Every sensor except the profile ones maps to a snapshot section."""
        keys = {d.key for d in SENSORS}
        profile = {
            "weight",
            "height",
            "ftp",
            "max_heart_rate",
            "ftp_source",
            "units",
            "name",
            "country",
        }

        assert set(SENSOR_SECTIONS) == keys - profile
        assert all(hasattr(RouvySnapshot, section) for section in SENSOR_SECTIONS.values())

    @pytest.mark.parametrize("entity_id", NUMERIC_SENSORS)
    async def test_numeric_sensors_record_statistics(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, entity_id: str
    ) -> None:
        """Numeric sensors keep a state class so HA's long-term statistics stay valid."""
        state = hass.states.get(entity_id)

        assert state is not None
        assert state.attributes.get("state_class") is not None

    async def test_statistics_metadata_is_reviewed(self, snapshot: SnapshotAssertion) -> None:
        """Changing a sensor's class, unit, or category shows up as a snapshot diff."""
        metadata = {
            d.key: {
                "device_class": d.device_class,
                "state_class": d.state_class,
                "unit": d.native_unit_of_measurement,
                "entity_category": d.entity_category,
                "enabled_by_default": d.entity_registry_enabled_default,
            }
            for d in SENSORS
        }

        assert metadata == snapshot

    async def test_every_description_has_unique_key(self) -> None:
        """Sensor keys are unique."""
        keys = [d.key for d in SENSORS]

        assert len(keys) == len(set(keys))


class TestSensorAvailability:
    """Sections that fail to load make only their sensors unavailable."""

    async def test_failed_section_is_unavailable(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """A failing events endpoint marks event sensors unavailable but not the others."""
        fake_rouvy.state.failures[Endpoint.EVENTS] = 500
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        next_event = hass.states.get("sensor.rouvy_next_event")
        weight = hass.states.get("sensor.rouvy_weight")

        assert next_event is not None
        assert next_event.state == STATE_UNAVAILABLE
        assert weight is not None
        assert weight.state == "85.0"

    async def test_no_joined_event_is_unknown(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        payloads: RouvyPayloads,
    ) -> None:
        """With events loaded but none joined, next-event sensors are unknown, not unavailable."""
        fake_rouvy.state.bodies[Endpoint.EVENTS] = payloads.captured(Endpoint.EVENTS)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        next_event = hass.states.get("sensor.rouvy_next_event")
        upcoming = hass.states.get("sensor.rouvy_upcoming_events")

        assert next_event is not None
        assert next_event.state == STATE_UNKNOWN
        assert upcoming is not None
        assert upcoming.state == "0"


class TestSnapshotView:
    """Derived values for sparse snapshots."""

    @staticmethod
    def snapshot(**sections: object) -> RouvySnapshot:
        """Return a snapshot with only the given sections."""
        return RouvySnapshot(
            profile=UserProfile(),
            fetched_at=datetime(2026, 10, 10, tzinfo=UTC),
            **sections,  # ty: ignore[invalid-argument-type]  # test helper passes section models
        )

    def test_empty_sections(self) -> None:
        """Missing sections produce no values instead of errors."""
        empty = self.snapshot()

        assert SnapshotView.week_total(empty, lambda t: t.distance_m) is None
        assert SnapshotView.last_activity(empty) is None
        assert SnapshotView.period(empty, yearly=True) is None
        assert SnapshotView.zones(empty, ZoneType.POWER) is None
        assert SnapshotView.next_event(empty) is None

    def test_no_activity_this_week_is_zero(self) -> None:
        """Weekly totals are zero when Rouvy has no row for the current week."""
        snapshot = self.snapshot(weekly_stats=(WeeklyActivityStats(),))

        assert SnapshotView.week_total(snapshot, lambda t: t.distance_m) == 0.0

    def test_zones_without_values(self) -> None:
        """Zones with no boundaries report no value."""
        assert SnapshotView.zones(self.snapshot(zones=TrainingZones()), ZoneType.POWER) is None

    def test_last_activity_without_start(self) -> None:
        """Activities without a start time sort before dated ones."""
        dated = Activity("b", started_at=datetime(2026, 1, 1, tzinfo=UTC))
        overview = ProfileOverview(recent_activities=(Activity("a"), dated))

        assert SnapshotView.last_activity(self.snapshot(overview=overview)) is dated
