"""Sensor platform for the Rouvy integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from custom_components.rouvy.coordinator import (
    RouvyConfigEntry,
    RouvyDataUpdateCoordinator,
    RouvySnapshot,
)
from custom_components.rouvy.entity import RouvyEntity
from custom_components.rouvy.rouvy_api import (
    Activity,
    ActivityTypeTotals,
    Event,
    PeriodTotals,
    ZoneType,
)

type StateValue = str | int | float | datetime | None
type AttributeValue = str | int | float | bool | list[int] | None

PARALLEL_UPDATES = 0
_KM = 1000.0
_MINUTE = 60.0
_HOUR = 3600.0
_BPM = "bpm"


class SnapshotView:
    """Derived values shared by several sensor descriptions."""

    @staticmethod
    def week_total(
        snapshot: RouvySnapshot, getter: Callable[[ActivityTypeTotals], float]
    ) -> float | None:
        """Sum one weekly total across every activity type for the current week."""
        week = snapshot.current_week(dt_util.now().date())
        if snapshot.weekly_stats is None:
            return None
        if week is None:
            return 0.0
        parts: tuple[ActivityTypeTotals, ...] = (week.ride, week.workout, week.event, week.outdoor)
        return float(sum(getter(part) for part in parts))

    @staticmethod
    def last_activity(snapshot: RouvySnapshot) -> Activity | None:
        """Return the most recent activity."""
        if snapshot.overview is None or not snapshot.overview.recent_activities:
            return None
        return max(
            snapshot.overview.recent_activities,
            key=lambda a: a.started_at or datetime.min.replace(tzinfo=dt_util.UTC),
        )

    @staticmethod
    def period(snapshot: RouvySnapshot, *, yearly: bool) -> PeriodTotals | None:
        """Return year- or month-to-date totals."""
        if snapshot.overview is None:
            return None
        return snapshot.overview.year_totals if yearly else snapshot.overview.month_totals

    @staticmethod
    def zones(snapshot: RouvySnapshot, zone_type: ZoneType) -> str | None:
        """Return zone boundaries as a comma-separated string."""
        if snapshot.zones is None:
            return None
        values = snapshot.zones.zones_for(zone_type)
        return ", ".join(str(v) for v in values) if values else None

    @staticmethod
    def next_event(snapshot: RouvySnapshot) -> Event | None:
        """Return the soonest upcoming event."""
        events = snapshot.upcoming_events(dt_util.utcnow())
        return events[0] if events is not None and len(events) > 0 else None

    @staticmethod
    def activity_value(
        snapshot: RouvySnapshot, getter: Callable[[Activity], StateValue]
    ) -> StateValue:
        """Apply a getter to the last activity."""
        activity = SnapshotView.last_activity(snapshot)
        return getter(activity) if activity is not None else None

    @staticmethod
    def period_value(
        snapshot: RouvySnapshot,
        getter: Callable[[PeriodTotals], float],
        *,
        yearly: bool,
        scale: float = 1.0,
    ) -> float | None:
        """Return a period total in display units."""
        totals = SnapshotView.period(snapshot, yearly=yearly)
        return getter(totals) / scale if totals is not None else None

    @staticmethod
    def scaled(value: float | None, scale: float) -> float | None:
        """Divide a value by a scale, preserving None."""
        return value / scale if value is not None else None

    @staticmethod
    def count[T](
        items: tuple[T, ...] | None, predicate: Callable[[T], bool] | None = None
    ) -> int | None:
        """Count items, optionally filtered; None when the section is unavailable."""
        if items is None:
            return None
        return sum(1 for item in items if predicate is None or predicate(item))


@dataclass(frozen=True, kw_only=True)
class RouvySensorDescription(SensorEntityDescription):
    """Describe a Rouvy sensor."""

    value_fn: Callable[[RouvySnapshot], StateValue]
    attributes_fn: Callable[[RouvySnapshot], Mapping[str, AttributeValue]] | None = None


# Snapshot section each sensor depends on; profile sensors need only the profile.
# A sensor is unavailable when its section failed to load, and "unknown" when the
# section loaded but has no value (for example, no joined events).
SENSOR_SECTIONS: Final[dict[str, str]] = {
    **dict.fromkeys(
        (
            "weekly_distance",
            "weekly_elevation",
            "weekly_calories",
            "weekly_ride_time",
            "weekly_ride_count",
            "weekly_training_score",
        ),
        "weekly_stats",
    ),
    **dict.fromkeys(
        (
            "monthly_distance",
            "monthly_ride_time",
            "yearly_distance",
            "yearly_elevation",
            "yearly_ride_time",
            "last_activity_title",
            "last_activity_distance",
            "last_activity_duration",
            "last_activity_date",
            "total_activities",
            "career_level",
            "total_xp",
            "friends_count",
            "friends_online",
        ),
        "overview",
    ),
    **dict.fromkeys(("active_challenges", "completed_challenges"), "challenges"),
    **dict.fromkeys(("upcoming_events_count", "next_event", "next_event_time"), "events"),
    **dict.fromkeys(("favorite_routes_count", "routes_online_riders"), "favorite_routes"),
    "career_achievements": "achievements",
    "career_trophies": "trophies",
    **dict.fromkeys(("power_zones", "hr_zones"), "zones"),
    **dict.fromkeys(("connected_apps_count", "connected_apps_active"), "connected_apps"),
}

SENSORS: tuple[RouvySensorDescription, ...] = (
    # Profile
    RouvySensorDescription(
        key="weight",
        translation_key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.profile.weight_kg,
    ),
    RouvySensorDescription(
        key="height",
        translation_key="height",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.profile.height_cm,
    ),
    RouvySensorDescription(
        key="ftp",
        translation_key="ftp",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.profile.effective_ftp_watts,
    ),
    RouvySensorDescription(
        key="max_heart_rate",
        translation_key="max_heart_rate",
        native_unit_of_measurement=_BPM,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.profile.max_heart_rate,
    ),
    RouvySensorDescription(
        key="ftp_source",
        translation_key="ftp_source",
        device_class=SensorDeviceClass.ENUM,
        options=["manual", "estimated"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: (
            s.profile.ftp_source.lower() if s.profile.ftp_source is not None else None
        ),
    ),
    RouvySensorDescription(
        key="units",
        translation_key="units",
        device_class=SensorDeviceClass.ENUM,
        options=["metric", "imperial"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.profile.units.lower(),
    ),
    RouvySensorDescription(
        key="name",
        translation_key="name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.profile.display_name,
    ),
    RouvySensorDescription(
        key="country",
        translation_key="country",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.profile.country,
    ),
    # Current week (all activity types)
    RouvySensorDescription(
        key="weekly_distance",
        translation_key="weekly_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.scaled(
            SnapshotView.week_total(s, lambda t: t.distance_m), _KM
        ),
    ),
    RouvySensorDescription(
        key="weekly_elevation",
        translation_key="weekly_elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.week_total(s, lambda t: t.elevation_m),
    ),
    RouvySensorDescription(
        key="weekly_calories",
        translation_key="weekly_calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.week_total(s, lambda t: t.calories_kcal),
    ),
    RouvySensorDescription(
        key="weekly_ride_time",
        translation_key="weekly_ride_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.scaled(
            SnapshotView.week_total(s, lambda t: t.moving_time_s), _MINUTE
        ),
    ),
    RouvySensorDescription(
        key="weekly_ride_count",
        translation_key="weekly_ride_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: (
            round(count)
            if (count := SnapshotView.week_total(s, lambda t: t.activity_count)) is not None
            else None
        ),
    ),
    RouvySensorDescription(
        key="weekly_training_score",
        translation_key="weekly_training_score",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.week_total(s, lambda t: t.training_score),
    ),
    # Month and year to date
    RouvySensorDescription(
        key="monthly_distance",
        translation_key="monthly_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.period_value(
            s, lambda t: t.distance_m, yearly=False, scale=_KM
        ),
    ),
    RouvySensorDescription(
        key="monthly_ride_time",
        translation_key="monthly_ride_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.period_value(
            s, lambda t: t.duration_s, yearly=False, scale=_HOUR
        ),
    ),
    RouvySensorDescription(
        key="yearly_distance",
        translation_key="yearly_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.period_value(
            s, lambda t: t.distance_m, yearly=True, scale=_KM
        ),
    ),
    RouvySensorDescription(
        key="yearly_elevation",
        translation_key="yearly_elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.period_value(
            s, lambda t: t.ascent_m, yearly=True, scale=1.0
        ),
    ),
    RouvySensorDescription(
        key="yearly_ride_time",
        translation_key="yearly_ride_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.period_value(
            s, lambda t: t.duration_s, yearly=True, scale=_HOUR
        ),
    ),
    # Last activity
    RouvySensorDescription(
        key="last_activity_title",
        translation_key="last_activity_title",
        value_fn=lambda s: SnapshotView.activity_value(s, lambda a: a.title or a.training_type),
    ),
    RouvySensorDescription(
        key="last_activity_distance",
        translation_key="last_activity_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: SnapshotView.activity_value(s, lambda a: a.distance_m / _KM),
    ),
    RouvySensorDescription(
        key="last_activity_duration",
        translation_key="last_activity_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: SnapshotView.activity_value(s, lambda a: a.moving_time_s / _MINUTE),
    ),
    RouvySensorDescription(
        key="last_activity_date",
        translation_key="last_activity_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: SnapshotView.activity_value(s, lambda a: a.started_at),
    ),
    RouvySensorDescription(
        key="total_activities",
        translation_key="total_activities",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(s.overview.recent_activities) if s.overview else None,
    ),
    # Challenges, events, routes
    RouvySensorDescription(
        key="active_challenges",
        translation_key="active_challenges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.challenges, lambda c: c.is_active),
        attributes_fn=lambda s: {
            "challenges": ", ".join(
                c.title or c.challenge_id for c in s.challenges or () if c.is_active
            )
        },
    ),
    RouvySensorDescription(
        key="completed_challenges",
        translation_key="completed_challenges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.challenges, lambda c: c.is_done),
    ),
    RouvySensorDescription(
        key="upcoming_events_count",
        translation_key="upcoming_events_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.upcoming_events(dt_util.utcnow())),
    ),
    RouvySensorDescription(
        key="next_event",
        translation_key="next_event",
        value_fn=lambda s: e.title if (e := SnapshotView.next_event(s)) else None,
        attributes_fn=lambda s: {
            "event_id": e.event_id if (e := SnapshotView.next_event(s)) else None
        },
    ),
    RouvySensorDescription(
        key="next_event_time",
        translation_key="next_event_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: e.starts_at if (e := SnapshotView.next_event(s)) else None,
    ),
    RouvySensorDescription(
        key="favorite_routes_count",
        translation_key="favorite_routes_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.favorite_routes),
    ),
    RouvySensorDescription(
        key="routes_online_riders",
        translation_key="routes_online_riders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: (
            sum(r.online_count for r in s.favorite_routes)
            if s.favorite_routes is not None
            else None
        ),
    ),
    # Career and social
    RouvySensorDescription(
        key="career_level",
        translation_key="career_level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.overview.career.level if s.overview and s.overview.career else None,
    ),
    RouvySensorDescription(
        key="total_xp",
        translation_key="total_xp",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: (
            s.overview.career.experience_points if s.overview and s.overview.career else None
        ),
    ),
    RouvySensorDescription(
        key="career_achievements",
        translation_key="career_achievements",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.achievements.earned if s.achievements else None,
        attributes_fn=lambda s: {"available": s.achievements.total if s.achievements else None},
    ),
    RouvySensorDescription(
        key="career_trophies",
        translation_key="career_trophies",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.trophies.total if s.trophies else None,
    ),
    RouvySensorDescription(
        key="friends_count",
        translation_key="friends_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.overview.friends.total if s.overview and s.overview.friends else None,
    ),
    RouvySensorDescription(
        key="friends_online",
        translation_key="friends_online",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.overview.friends.online if s.overview and s.overview.friends else None,
    ),
    # Configuration
    RouvySensorDescription(
        key="power_zones",
        translation_key="power_zones",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: SnapshotView.zones(s, ZoneType.POWER),
    ),
    RouvySensorDescription(
        key="hr_zones",
        translation_key="hr_zones",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: SnapshotView.zones(s, ZoneType.HEART_RATE),
    ),
    RouvySensorDescription(
        key="connected_apps_count",
        translation_key="connected_apps_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.connected_apps),
    ),
    RouvySensorDescription(
        key="connected_apps_active",
        translation_key="connected_apps_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: SnapshotView.count(s.connected_apps, lambda a: a.is_active),
        attributes_fn=lambda s: {
            "apps": ", ".join(a.name for a in s.connected_apps or () if a.is_active)
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 - HA signature
    entry: RouvyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one sensor per description."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(RouvySensor(coordinator, description) for description in SENSORS)


class RouvySensor(RouvyEntity, SensorEntity):
    """A sensor whose value is derived from the coordinator snapshot."""

    def __init__(
        self, coordinator: RouvyDataUpdateCoordinator, description: RouvySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._description = description
        self._refresh_state()

    @property
    @override
    def available(self) -> bool:
        """Return False when the backing section could not be fetched."""
        if not super().available:
            return False
        section = SENSOR_SECTIONS.get(self._description.key)
        return section is None or getattr(self.coordinator.data, section) is not None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Recompute the state from the new snapshot."""
        self._refresh_state()
        super()._handle_coordinator_update()

    def _refresh_state(self) -> None:
        """Derive the value and attributes from the current snapshot."""
        snapshot = self.coordinator.data
        self._attr_native_value = self._description.value_fn(snapshot)
        attributes_fn = self._description.attributes_fn
        self._attr_extra_state_attributes = (
            dict(attributes_fn(snapshot)) if attributes_fn is not None else {}
        )
