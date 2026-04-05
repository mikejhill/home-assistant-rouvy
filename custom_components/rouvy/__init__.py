"""The Rouvy integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import RouvyConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
) -> bool:
    """Set up Rouvy from a config entry."""
    from homeassistant.const import Platform
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.loader import async_get_loaded_integration

    from .api import RouvyAsyncApiClient
    from .const import CONF_EMAIL, CONF_PASSWORD
    from .coordinator import RouvyDataUpdateCoordinator
    from .data import RouvyData

    _LOGGER.debug("Setting up Rouvy integration for %s", entry.data.get(CONF_EMAIL))

    client = RouvyAsyncApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    coordinator = RouvyDataUpdateCoordinator(hass, entry)
    entry.runtime_data = RouvyData(
        client=client,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    _register_services(hass)

    _LOGGER.info("Rouvy integration setup complete for %s", entry.data.get(CONF_EMAIL))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RouvyConfigEntry,
) -> bool:
    """Unload a Rouvy config entry."""
    from homeassistant.const import Platform

    _LOGGER.debug("Unloading Rouvy integration")
    result: bool = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    return result


def _register_services(hass: Any) -> None:
    """Register Rouvy services (idempotent — safe to call multiple times)."""
    from .const import DOMAIN

    async def _handle_update_weight(call: Any) -> None:
        weight = call.data["weight"]
        _LOGGER.info("Service call: update_weight to %s", weight)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings({"weight": weight})
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_update_height(call: Any) -> None:
        height = call.data["height"]
        _LOGGER.info("Service call: update_height to %s", height)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings({"height": height})
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_update_settings(call: Any) -> None:
        settings = dict(call.data["settings"])
        _LOGGER.info("Service call: update_settings %s", settings)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_update_user_settings(settings)
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_register_challenge(call: Any) -> None:
        slug = call.data["slug"]
        _LOGGER.info("Service call: register_challenge for %s", slug)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_register_challenge(slug)
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_register_event(call: Any) -> None:
        event_id = call.data["event_id"]
        _LOGGER.info("Service call: register_event for %s", event_id)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_register_event(event_id)
                await entry.runtime_data.coordinator.async_request_refresh()

    async def _handle_unregister_event(call: Any) -> None:
        event_id = call.data["event_id"]
        _LOGGER.info("Service call: unregister_event for %s", event_id)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                client = entry.runtime_data.client
                await client.async_unregister_event(event_id)
                await entry.runtime_data.coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "update_weight"):
        hass.services.async_register(DOMAIN, "update_weight", _handle_update_weight)
    if not hass.services.has_service(DOMAIN, "update_height"):
        hass.services.async_register(DOMAIN, "update_height", _handle_update_height)
    if not hass.services.has_service(DOMAIN, "update_settings"):
        hass.services.async_register(DOMAIN, "update_settings", _handle_update_settings)
    if not hass.services.has_service(DOMAIN, "register_challenge"):
        hass.services.async_register(DOMAIN, "register_challenge", _handle_register_challenge)
    if not hass.services.has_service(DOMAIN, "register_event"):
        hass.services.async_register(DOMAIN, "register_event", _handle_register_event)
    if not hass.services.has_service(DOMAIN, "unregister_event"):
        hass.services.async_register(DOMAIN, "unregister_event", _handle_unregister_event)
