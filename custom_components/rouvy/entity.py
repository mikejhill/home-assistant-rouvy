"""Base entity for Rouvy sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.rouvy.const import DOMAIN
from custom_components.rouvy.coordinator import RouvyDataUpdateCoordinator


class RouvyEntity(CoordinatorEntity[RouvyDataUpdateCoordinator]):
    """Entity attached to the Rouvy account's service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RouvyDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Rouvy",
            manufacturer="Rouvy",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://riders.rouvy.com/profile/overview",
        )
