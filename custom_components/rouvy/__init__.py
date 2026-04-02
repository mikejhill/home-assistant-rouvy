"""The Rouvy integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import RouvyAsyncApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, LOGGER
from .coordinator import RouvyDataUpdateCoordinator
from .data import RouvyConfigEntry, RouvyData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
) -> bool:
    """Set up Rouvy from a config entry."""
    client = RouvyAsyncApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    coordinator = RouvyDataUpdateCoordinator(hass)
    entry.runtime_data = RouvyData(
        client=client,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
) -> bool:
    """Unload a Rouvy config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _register_services(hass: HomeAssistant) -> None:
    """Register Rouvy services (idempotent — safe to call multiple times)."""

    async def _handle_update_weight(call: ServiceCall) -> None:
        weight = call.data["weight"]
        LOGGER.info("Service call: update_weight to %s", weight)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings({"weight": weight})
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_update_height(call: ServiceCall) -> None:
        height = call.data["height"]
        LOGGER.info("Service call: update_height to %s", height)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings({"height": height})
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_update_settings(call: ServiceCall) -> None:
        settings = dict(call.data["settings"])
        LOGGER.info("Service call: update_settings %s", settings)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings(settings)
                await entry.runtime_data.coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "update_weight"):
        hass.services.async_register(DOMAIN, "update_weight", _handle_update_weight)
    if not hass.services.has_service(DOMAIN, "update_height"):
        hass.services.async_register(DOMAIN, "update_height", _handle_update_height)
    if not hass.services.has_service(DOMAIN, "update_settings"):
        hass.services.async_register(DOMAIN, "update_settings", _handle_update_settings)
