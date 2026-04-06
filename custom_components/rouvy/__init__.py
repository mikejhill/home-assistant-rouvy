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
    from dataclasses import asdict

    from homeassistant.core import SupportsResponse

    from .const import DOMAIN

    def _first_client(hass: Any) -> Any:
        """Return the first available RouvyAsyncApiClient, or raise."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                return entry.runtime_data
        msg = "No Rouvy integration configured"
        raise ValueError(msg)

    async def _handle_update_weight(call: Any) -> None:
        weight = call.data["weight"]
        _LOGGER.info("Service call: update_weight to %s", weight)
        rd = _first_client(hass)
        await rd.client.async_update_user_settings({"weight": weight})
        await rd.coordinator.async_request_refresh()

    async def _handle_update_height(call: Any) -> None:
        height = call.data["height"]
        _LOGGER.info("Service call: update_height to %s", height)
        rd = _first_client(hass)
        await rd.client.async_update_user_settings({"height": height})
        await rd.coordinator.async_request_refresh()

    async def _handle_update_settings(call: Any) -> None:
        settings = dict(call.data["settings"])
        _LOGGER.info("Service call: update_settings %s", settings)
        rd = _first_client(hass)
        await rd.client.async_update_user_settings(settings)
        await rd.coordinator.async_request_refresh()

    async def _handle_update_profile(call: Any) -> None:
        updates: dict[str, Any] = {}
        for key in ("userName", "firstName", "team"):
            if key in call.data:
                updates[key] = call.data[key]
        rd = _first_client(hass)
        if "accountPrivacy" in call.data:
            _LOGGER.info("Service call: update_social %s", call.data["accountPrivacy"])
            await rd.client.async_update_user_social(call.data["accountPrivacy"])
        if updates:
            _LOGGER.info("Service call: update_profile %s", updates)
            await rd.client.async_update_user_profile(updates)
        await rd.coordinator.async_request_refresh()

    async def _handle_update_units(call: Any) -> None:
        units = call.data["units"]
        _LOGGER.info("Service call: update_units to %s", units)
        rd = _first_client(hass)
        await rd.client.async_update_user_settings({"units": units})
        await rd.coordinator.async_request_refresh()

    async def _handle_update_timezone(call: Any) -> None:
        timezone = call.data["timezone"]
        _LOGGER.info("Service call: update_timezone to %s", timezone)
        rd = _first_client(hass)
        await rd.client.async_update_timezone(timezone)
        await rd.coordinator.async_request_refresh()

    async def _handle_update_ftp(call: Any) -> None:
        ftp_source = call.data["ftp_source"]
        value = call.data.get("value")
        _LOGGER.info("Service call: update_ftp source=%s value=%s", ftp_source, value)
        rd = _first_client(hass)
        await rd.client.async_update_ftp(ftp_source, value)
        await rd.coordinator.async_request_refresh()

    async def _handle_update_zones(call: Any) -> None:
        zone_type = call.data["zone_type"]
        zones = list(call.data["zones"])
        _LOGGER.info("Service call: update_zones type=%s zones=%s", zone_type, zones)
        rd = _first_client(hass)
        await rd.client.async_update_zones(zone_type, zones)
        await rd.coordinator.async_request_refresh()

    async def _handle_register_challenge(call: Any) -> None:
        slug = call.data["slug"]
        _LOGGER.info("Service call: register_challenge for %s", slug)
        rd = _first_client(hass)
        await rd.client.async_register_challenge(slug)
        await rd.coordinator.async_request_refresh()

    async def _handle_register_event(call: Any) -> None:
        event_id = call.data["event_id"]
        _LOGGER.info("Service call: register_event for %s", event_id)
        rd = _first_client(hass)
        await rd.client.async_register_event(event_id)
        await rd.coordinator.async_request_refresh()

    async def _handle_unregister_event(call: Any) -> None:
        event_id = call.data["event_id"]
        _LOGGER.info("Service call: unregister_event for %s", event_id)
        rd = _first_client(hass)
        await rd.client.async_unregister_event(event_id)
        await rd.coordinator.async_request_refresh()

    # Query services return data via SupportsResponse
    async def _handle_get_profile(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_profile")
        rd = _first_client(hass)
        profile = await rd.client.async_get_user_profile()
        return {"profile": asdict(profile)}

    async def _handle_get_events(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_events")
        rd = _first_client(hass)
        events = await rd.client.async_get_events()
        return {"events": [asdict(e) for e in events]}

    async def _handle_get_challenges(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_challenges")
        rd = _first_client(hass)
        challenges = await rd.client.async_get_challenges()
        return {"challenges": [asdict(c) for c in challenges]}

    async def _handle_get_routes(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_routes")
        rd = _first_client(hass)
        routes = await rd.client.async_get_favorite_routes()
        return {"routes": [asdict(r) for r in routes]}

    async def _handle_get_activities(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_activities")
        rd = _first_client(hass)
        summary = await rd.client.async_get_activity_summary()
        return {"activities": [asdict(a) for a in summary.recent_activities]}

    async def _handle_get_career(_call: Any) -> dict[str, Any]:
        _LOGGER.info("Service call: get_career")
        rd = _first_client(hass)
        career = await rd.client.async_get_career()
        return {"career": asdict(career)}

    # Register update services
    _svc = [
        ("update_weight", _handle_update_weight, None),
        ("update_height", _handle_update_height, None),
        ("update_settings", _handle_update_settings, None),
        ("update_profile", _handle_update_profile, None),
        ("update_units", _handle_update_units, None),
        ("update_timezone", _handle_update_timezone, None),
        ("update_ftp", _handle_update_ftp, None),
        ("update_zones", _handle_update_zones, None),
        ("register_challenge", _handle_register_challenge, None),
        ("register_event", _handle_register_event, None),
        ("unregister_event", _handle_unregister_event, None),
        ("get_profile", _handle_get_profile, SupportsResponse.ONLY),
        ("get_events", _handle_get_events, SupportsResponse.ONLY),
        ("get_challenges", _handle_get_challenges, SupportsResponse.ONLY),
        ("get_routes", _handle_get_routes, SupportsResponse.ONLY),
        ("get_activities", _handle_get_activities, SupportsResponse.ONLY),
        ("get_career", _handle_get_career, SupportsResponse.ONLY),
    ]

    for name, handler, supports_response in _svc:
        if not hass.services.has_service(DOMAIN, name):
            kwargs: dict[str, Any] = {}
            if supports_response is not None:
                kwargs["supports_response"] = supports_response
            hass.services.async_register(DOMAIN, name, handler, **kwargs)
