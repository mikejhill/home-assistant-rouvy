"""Sensor platform for the Rouvy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from rouvy_api_client.models import UserProfile

from .data import RouvyConfigEntry
from .entity import RouvyEntity


@dataclass(frozen=True, kw_only=True)
class RouvySensorDescription(SensorEntityDescription):
    """Describe a Rouvy sensor."""

    value_fn: Callable[[UserProfile], Any]


SENSOR_DESCRIPTIONS: tuple[RouvySensorDescription, ...] = (
    RouvySensorDescription(
        key="weight",
        translation_key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda p: p.weight_kg if p.weight_kg else None,
    ),
    RouvySensorDescription(
        key="height",
        translation_key="height",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda p: p.height_cm if p.height_cm else None,
    ),
    RouvySensorDescription(
        key="ftp",
        translation_key="ftp",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda p: p.ftp_watts if p.ftp_watts else None,
    ),
    RouvySensorDescription(
        key="max_heart_rate",
        translation_key="max_heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda p: p.max_heart_rate,
    ),
    RouvySensorDescription(
        key="units",
        translation_key="units",
        value_fn=lambda p: p.units,
    ),
    RouvySensorDescription(
        key="name",
        translation_key="name",
        value_fn=lambda p: (
            f"{p.first_name} {p.last_name}".strip() or p.username or None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rouvy sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        RouvySensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class RouvySensor(RouvyEntity, SensorEntity):
    """A Rouvy sensor entity backed by the coordinator."""

    entity_description: RouvySensorDescription

    def __init__(
        self,
        coordinator: "RouvyDataUpdateCoordinator",
        description: RouvySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{description.key}"
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
