"""The Rouvy integration: sensors and actions for a Rouvy indoor cycling account."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from custom_components.rouvy.api import RouvyClientFactory
from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from custom_components.rouvy.coordinator import (
    RouvyConfigEntry,
    RouvyDataUpdateCoordinator,
    RouvyRuntimeData,
)
from custom_components.rouvy.services import RouvyServices

PLATFORMS: Final = [Platform.SENSOR]
CONFIG_SCHEMA: Final = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001 - HA signature
    """Register the integration's actions once, independent of config entries."""
    RouvyServices(hass).register()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RouvyConfigEntry) -> bool:
    """Log in, fetch the first snapshot, and set up platforms."""
    connection = RouvyClientFactory.connect(hass, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    entry.async_on_unload(connection.release)
    coordinator = RouvyDataUpdateCoordinator(hass, entry, connection.client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = RouvyRuntimeData(coordinator=coordinator, connection=connection)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RouvyConfigEntry) -> bool:
    """Unload platforms; the session is released by the on-unload callback."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
