"""Base entity for the Rouvy integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RouvyDataUpdateCoordinator


class RouvyEntity(CoordinatorEntity[RouvyDataUpdateCoordinator]):
    """Base entity for Rouvy sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RouvyDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Rouvy",
            manufacturer="VirtualTraining / Rouvy",
            entry_type=DeviceEntryType.SERVICE,
        )
