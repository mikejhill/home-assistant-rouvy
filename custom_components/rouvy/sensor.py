"""Sensor platform for the Rouvy integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client.models import Activity, ActivityTypeStats, RouvyCoordinatorData
from .data import RouvyConfigEntry
from .entity import RouvyEntity

if TYPE_CHECKING:
    from .coordinator import RouvyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _current_week_ride_stats(data: RouvyCoordinatorData) -> ActivityTypeStats | None:
    """Get ride stats for the current (first) week, or None."""
    if not data.activity_stats:
        return None
    return data.activity_stats[0].ride


def _challenge_counts(data: RouvyCoordinatorData) -> tuple[int, int] | None:
    """Return (active, completed) challenge counts, or None if no data."""
    if not data.challenges:
        return None
    active = sum(1 for c in data.challenges if c.registered and not c.is_done)
    completed = sum(1 for c in data.challenges if c.is_done)
    return active, completed


def _last_activity(data: RouvyCoordinatorData) -> Activity | None:
    """Get the most recent activity, or None."""
    if data.activity_summary and data.activity_summary.recent_activities:
        return data.activity_summary.recent_activities[0]
    return None


@dataclass(frozen=True, kw_only=True)
class RouvySensorDescription(SensorEntityDescription):
    """Describe a Rouvy sensor."""

    value_fn: Callable[[RouvyCoordinatorData], Any]


SENSOR_DESCRIPTIONS: tuple[RouvySensorDescription, ...] = (
    # Profile sensors
    RouvySensorDescription(
        key="weight",
        translation_key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.profile.weight_kg if d.profile.weight_kg else None,
    ),
    RouvySensorDescription(
        key="height",
        translation_key="height",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.profile.height_cm if d.profile.height_cm else None,
    ),
    RouvySensorDescription(
        key="ftp",
        translation_key="ftp",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.profile.ftp_watts if d.profile.ftp_watts else None,
    ),
    RouvySensorDescription(
        key="max_heart_rate",
        translation_key="max_heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.profile.max_heart_rate,
    ),
    RouvySensorDescription(
        key="units",
        translation_key="units",
        value_fn=lambda d: d.profile.units,
    ),
    RouvySensorDescription(
        key="name",
        translation_key="name",
        value_fn=lambda d: (
            f"{d.profile.first_name} {d.profile.last_name}".strip() or d.profile.username or None
        ),
    ),
    RouvySensorDescription(
        key="ftp_source",
        translation_key="ftp_source",
        value_fn=lambda d: d.profile.ftp_source or None,
    ),
    RouvySensorDescription(
        key="country",
        translation_key="country",
        value_fn=lambda d: d.profile.country,
    ),
    # Weekly activity stats sensors (current week ride totals)
    RouvySensorDescription(
        key="weekly_distance",
        translation_key="weekly_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda d: (
            round(s.distance_m / 1000, 1) if (s := _current_week_ride_stats(d)) else None
        ),
    ),
    RouvySensorDescription(
        key="weekly_elevation",
        translation_key="weekly_elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda d: round(s.elevation_m) if (s := _current_week_ride_stats(d)) else None,
    ),
    RouvySensorDescription(
        key="weekly_calories",
        translation_key="weekly_calories",
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda d: round(s.calories) if (s := _current_week_ride_stats(d)) else None,
    ),
    RouvySensorDescription(
        key="weekly_ride_time",
        translation_key="weekly_ride_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda d: (
            round(s.moving_time_seconds / 60) if (s := _current_week_ride_stats(d)) else None
        ),
    ),
    RouvySensorDescription(
        key="weekly_ride_count",
        translation_key="weekly_ride_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: s.activity_count if (s := _current_week_ride_stats(d)) else None,
    ),
    RouvySensorDescription(
        key="weekly_training_score",
        translation_key="weekly_training_score",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda d: round(s.training_score) if (s := _current_week_ride_stats(d)) else None,
    ),
    # Challenge sensors
    RouvySensorDescription(
        key="active_challenges",
        translation_key="active_challenges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: counts[0] if (counts := _challenge_counts(d)) else None,
    ),
    RouvySensorDescription(
        key="completed_challenges",
        translation_key="completed_challenges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: counts[1] if (counts := _challenge_counts(d)) else None,
    ),
    # Training zones sensors
    RouvySensorDescription(
        key="power_zones",
        translation_key="power_zones",
        value_fn=lambda d: (
            ", ".join(str(v) for v in d.training_zones.power_zone_values)
            if d.training_zones and d.training_zones.power_zone_values
            else None
        ),
    ),
    RouvySensorDescription(
        key="hr_zones",
        translation_key="hr_zones",
        value_fn=lambda d: (
            ", ".join(str(v) for v in d.training_zones.hr_zone_values)
            if d.training_zones and d.training_zones.hr_zone_values
            else None
        ),
    ),
    # Connected apps sensors
    RouvySensorDescription(
        key="connected_apps_count",
        translation_key="connected_apps_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.connected_apps) if d.connected_apps else 0,
    ),
    RouvySensorDescription(
        key="connected_apps_active",
        translation_key="connected_apps_active",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            sum(1 for a in d.connected_apps if a.status == "active") if d.connected_apps else 0
        ),
    ),
    # Activity summary sensors
    RouvySensorDescription(
        key="last_activity_title",
        translation_key="last_activity_title",
        value_fn=lambda d: a.title if (a := _last_activity(d)) else None,
    ),
    RouvySensorDescription(
        key="last_activity_distance",
        translation_key="last_activity_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
        value_fn=lambda d: round(a.distance_m / 1000, 1) if (a := _last_activity(d)) else None,
    ),
    RouvySensorDescription(
        key="last_activity_duration",
        translation_key="last_activity_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=0,
        value_fn=lambda d: round(a.moving_time_seconds / 60) if (a := _last_activity(d)) else None,
    ),
    RouvySensorDescription(
        key="last_activity_date",
        translation_key="last_activity_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: a.start_utc if (a := _last_activity(d)) else None,
    ),
    RouvySensorDescription(
        key="total_activities",
        translation_key="total_activities",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            len(d.activity_summary.recent_activities) if d.activity_summary else None
        ),
    ),
    # Route sensors
    RouvySensorDescription(
        key="favorite_routes_count",
        translation_key="favorite_routes_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.favorite_routes) if d.favorite_routes else 0,
    ),
    RouvySensorDescription(
        key="routes_online_riders",
        translation_key="routes_online_riders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            sum(r.online_count for r in d.favorite_routes) if d.favorite_routes else 0
        ),
    ),
    # Event sensors
    RouvySensorDescription(
        key="upcoming_events_count",
        translation_key="upcoming_events_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.upcoming_events) if d.upcoming_events else 0,
    ),
    RouvySensorDescription(
        key="next_event",
        translation_key="next_event",
        value_fn=lambda d: d.upcoming_events[0].title if d.upcoming_events else None,
    ),
    RouvySensorDescription(
        key="next_event_time",
        translation_key="next_event_time",
        value_fn=lambda d: d.upcoming_events[0].start_date_time if d.upcoming_events else None,
    ),
    # Career sensors
    RouvySensorDescription(
        key="career_level",
        translation_key="career_level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.career.level if d.career else None,
    ),
    RouvySensorDescription(
        key="total_xp",
        translation_key="total_xp",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.career.experience_points if d.career else None,
    ),
    RouvySensorDescription(
        key="total_coins",
        translation_key="total_coins",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.career.coins if d.career else None,
    ),
    RouvySensorDescription(
        key="career_total_distance",
        translation_key="career_total_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda d: (
            round(d.career.total_distance_m / 1000, 1)
            if d.career and d.career.total_distance_m
            else None
        ),
    ),
    RouvySensorDescription(
        key="career_total_elevation",
        translation_key="career_total_elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda d: round(d.career.total_elevation_m) if d.career else None,
    ),
    RouvySensorDescription(
        key="career_total_time",
        translation_key="career_total_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda d: (
            round(d.career.total_time_seconds / 3600, 1) if d.career else None
        ),
    ),
    RouvySensorDescription(
        key="career_total_activities",
        translation_key="career_total_activities",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.career.total_activities if d.career else None,
    ),
    RouvySensorDescription(
        key="career_achievements",
        translation_key="career_achievements",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.career.total_achievements if d.career else None,
    ),
    RouvySensorDescription(
        key="career_trophies",
        translation_key="career_trophies",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.career.total_trophies if d.career else None,
    ),
    # Friends sensors
    RouvySensorDescription(
        key="friends_count",
        translation_key="friends_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.friends.total_friends if d.friends else None,
    ),
    RouvySensorDescription(
        key="friends_online",
        translation_key="friends_online",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.friends.online_friends if d.friends else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rouvy sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    entities = [RouvySensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS]
    _LOGGER.debug("Creating %d sensor entities", len(entities))
    async_add_entities(entities)


class RouvySensor(RouvyEntity, SensorEntity):
    """A Rouvy sensor entity backed by the coordinator."""

    entity_description: RouvySensorDescription

    def __init__(
        self,
        coordinator: RouvyDataUpdateCoordinator,
        description: RouvySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
