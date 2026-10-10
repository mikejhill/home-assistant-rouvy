"""Actions (services) that change Rouvy settings or return Rouvy data."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Final

import probatio as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from custom_components.rouvy.const import DOMAIN
from custom_components.rouvy.coordinator import RouvyDataUpdateCoordinator, RouvyRuntimeData
from custom_components.rouvy.rouvy_api import (
    AccountPrivacy,
    FtpSource,
    JsonValue,
    ProfileUpdate,
    RouvyClient,
    RouvyError,
    RouvyValidationError,
    UnitSystem,
    ZoneType,
)

type UpdateAction = Callable[[RouvyClient, ServiceCall], Awaitable[None]]
type QueryAction = Callable[[RouvyClient], Awaitable[dict[str, JsonValue]]]

_IDENTIFIER: Final = vol.All(cv.string, vol.Match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"))
_UNITS: Final = vol.All(vol.Upper, vol.In([u.value for u in UnitSystem]))
_WEIGHT: Final = vol.All(vol.Coerce(float), vol.Range(min=20, max=250))
_HEIGHT: Final = vol.All(vol.Coerce(float), vol.Range(min=100, max=250))
_ZONES: Final = vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=300))])


@dataclass(frozen=True, slots=True)
class UpdateService:
    """An action that changes data and then refreshes the sensors."""

    schema: vol.Schema
    action: UpdateAction


class RouvyActions:
    """Implementations of every update and query action."""

    @staticmethod
    async def update_weight(client: RouvyClient, call: ServiceCall) -> None:
        """Set the weight."""
        await client.update_body_metrics(weight_kg=call.data["weight"])

    @staticmethod
    async def update_height(client: RouvyClient, call: ServiceCall) -> None:
        """Set the height."""
        await client.update_body_metrics(height_cm=call.data["height"])

    @staticmethod
    async def update_units(client: RouvyClient, call: ServiceCall) -> None:
        """Set the unit system."""
        await client.update_body_metrics(units=UnitSystem(call.data["units"]))

    @staticmethod
    async def update_settings(client: RouvyClient, call: ServiceCall) -> None:
        """Set any of weight, height, and units at once."""
        settings = call.data["settings"]
        units = settings.get("units")
        await client.update_body_metrics(
            weight_kg=settings.get("weight"),
            height_cm=settings.get("height"),
            units=UnitSystem(units) if units else None,
        )

    @staticmethod
    async def update_profile(client: RouvyClient, call: ServiceCall) -> None:
        """Set profile identity fields and/or account privacy."""
        data = call.data
        update = ProfileUpdate(
            username=data.get("userName"),
            first_name=data.get("firstName"),
            last_name=data.get("lastName"),
            country=data.get("countryIsoCode"),
            gender=data.get("gender"),
            birth_date=data.get("dateOfBirth"),
        )
        if update.is_empty and "accountPrivacy" not in data:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="profile_update_empty"
            )
        if "accountPrivacy" in data:
            await client.update_account_privacy(AccountPrivacy(data["accountPrivacy"]))
        if not update.is_empty:
            await client.update_profile(update)

    @staticmethod
    async def update_timezone(client: RouvyClient, call: ServiceCall) -> None:
        """Set the timezone."""
        await client.update_timezone(call.data["timezone"])

    @staticmethod
    async def update_ftp(client: RouvyClient, call: ServiceCall) -> None:
        """Set FTP to a manual value or back to the estimate."""
        await client.update_ftp(FtpSource(call.data["ftp_source"]), call.data.get("value"))

    @staticmethod
    async def update_zones(client: RouvyClient, call: ServiceCall) -> None:
        """Set zone boundaries."""
        await client.update_zones(ZoneType(call.data["zone_type"]), call.data["zones"])

    @staticmethod
    async def update_max_heart_rate(client: RouvyClient, call: ServiceCall) -> None:
        """Set the maximum heart rate."""
        await client.update_max_heart_rate(call.data["max_heart_rate"])

    @staticmethod
    async def register_challenge(client: RouvyClient, call: ServiceCall) -> None:
        """Join a challenge."""
        await client.register_challenge(call.data["slug"])

    @staticmethod
    async def register_event(client: RouvyClient, call: ServiceCall) -> None:
        """Join an event."""
        await client.register_event(call.data["event_id"])

    @staticmethod
    async def unregister_event(client: RouvyClient, call: ServiceCall) -> None:
        """Leave an event."""
        await client.unregister_event(call.data["event_id"])

    @staticmethod
    async def get_profile(client: RouvyClient) -> dict[str, JsonValue]:
        """Return the profile."""
        return {"profile": (await client.get_user_profile()).as_json()}

    @staticmethod
    async def get_events(client: RouvyClient) -> dict[str, JsonValue]:
        """Return upcoming events."""
        return {"events": [e.as_json() for e in await client.get_events()]}

    @staticmethod
    async def get_challenges(client: RouvyClient) -> dict[str, JsonValue]:
        """Return available challenges."""
        return {"challenges": [c.as_json() for c in await client.get_challenges()]}

    @staticmethod
    async def get_routes(client: RouvyClient) -> dict[str, JsonValue]:
        """Return favorite routes."""
        return {"routes": [r.as_json() for r in await client.get_favorite_routes()]}

    @staticmethod
    async def get_activities(client: RouvyClient) -> dict[str, JsonValue]:
        """Return recent activities."""
        overview = await client.get_profile_overview()
        return {"activities": [a.as_json() for a in overview.recent_activities]}

    @staticmethod
    async def get_career(client: RouvyClient) -> dict[str, JsonValue]:
        """Return career progress, achievements, and trophies."""
        overview = await client.get_profile_overview()
        achievements = await client.get_achievements()
        trophies = await client.get_trophies()
        return {
            "career": {
                **(overview.career.as_json() if overview.career else {}),
                "achievements": achievements.as_json(),
                "trophies": trophies.as_json(),
            }
        }


UPDATE_SERVICES: Final[dict[str, UpdateService]] = {
    "update_weight": UpdateService(
        vol.Schema({vol.Required("weight"): _WEIGHT}), RouvyActions.update_weight
    ),
    "update_height": UpdateService(
        vol.Schema({vol.Required("height"): _HEIGHT}), RouvyActions.update_height
    ),
    "update_units": UpdateService(
        vol.Schema({vol.Required("units"): _UNITS}), RouvyActions.update_units
    ),
    "update_settings": UpdateService(
        vol.Schema(
            {
                vol.Required("settings"): vol.All(
                    vol.Schema(
                        {
                            vol.Optional("weight"): _WEIGHT,
                            vol.Optional("height"): _HEIGHT,
                            vol.Optional("units"): _UNITS,
                        }
                    ),
                    vol.Length(min=1),
                )
            }
        ),
        RouvyActions.update_settings,
    ),
    "update_profile": UpdateService(
        vol.Schema(
            {
                vol.Optional("userName"): vol.All(cv.string, vol.Match(r"^[a-zA-Z0-9_.-]{4,25}$")),
                vol.Optional("firstName"): cv.string,
                vol.Optional("lastName"): cv.string,
                vol.Optional("countryIsoCode"): vol.All(cv.string, vol.Upper, vol.Length(2, 2)),
                vol.Optional("gender"): vol.All(vol.Upper, vol.In(["MALE", "FEMALE"])),
                vol.Optional("dateOfBirth"): cv.date,
                vol.Optional("accountPrivacy"): vol.All(
                    vol.Upper, vol.In([p.value for p in AccountPrivacy])
                ),
            }
        ),
        RouvyActions.update_profile,
    ),
    "update_timezone": UpdateService(
        vol.Schema({vol.Required("timezone"): cv.time_zone}), RouvyActions.update_timezone
    ),
    "update_ftp": UpdateService(
        vol.Schema(
            {
                vol.Required("ftp_source"): vol.All(
                    vol.Upper, vol.In([s.value for s in FtpSource])
                ),
                vol.Optional("value"): vol.All(vol.Coerce(int), vol.Range(min=50, max=700)),
            }
        ),
        RouvyActions.update_ftp,
    ),
    "update_zones": UpdateService(
        vol.Schema(
            {
                vol.Required("zone_type"): vol.In([z.value for z in ZoneType]),
                vol.Required("zones"): _ZONES,
            }
        ),
        RouvyActions.update_zones,
    ),
    "update_max_heart_rate": UpdateService(
        vol.Schema(
            {vol.Required("max_heart_rate"): vol.All(vol.Coerce(int), vol.Range(min=60, max=250))}
        ),
        RouvyActions.update_max_heart_rate,
    ),
    "register_challenge": UpdateService(
        vol.Schema({vol.Required("slug"): _IDENTIFIER}), RouvyActions.register_challenge
    ),
    "register_event": UpdateService(
        vol.Schema({vol.Required("event_id"): _IDENTIFIER}), RouvyActions.register_event
    ),
    "unregister_event": UpdateService(
        vol.Schema({vol.Required("event_id"): _IDENTIFIER}), RouvyActions.unregister_event
    ),
}
QUERY_SERVICES: Final[dict[str, QueryAction]] = {
    "get_profile": RouvyActions.get_profile,
    "get_events": RouvyActions.get_events,
    "get_challenges": RouvyActions.get_challenges,
    "get_routes": RouvyActions.get_routes,
    "get_activities": RouvyActions.get_activities,
    "get_career": RouvyActions.get_career,
}


class RouvyServices:
    """Register the integration's actions and route calls to the loaded entry."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def register(self) -> None:
        """Register every action."""
        for name, service in UPDATE_SERVICES.items():
            self._hass.services.async_register(
                DOMAIN, name, self._update_handler(service.action), schema=service.schema
            )
        for name, query in QUERY_SERVICES.items():
            self._hass.services.async_register(
                DOMAIN,
                name,
                self._query_handler(query),
                schema=vol.Schema({}),
                supports_response=SupportsResponse.ONLY,
            )

    def _update_handler(
        self, action: UpdateAction
    ) -> Callable[[ServiceCall], Coroutine[object, object, None]]:
        """Wrap an update action with error translation and a refresh."""

        async def handle(call: ServiceCall) -> None:
            coordinator = self._coordinator()
            await self._run(action(coordinator.client, call))
            await coordinator.async_request_refresh()

        return handle

    def _query_handler(
        self, query: QueryAction
    ) -> Callable[[ServiceCall], Coroutine[object, object, ServiceResponse]]:
        """Wrap a query action with error translation."""

        async def handle(call: ServiceCall) -> ServiceResponse:  # noqa: ARG001 - HA signature
            return await self._run(query(self._coordinator().client))

        return handle

    def _coordinator(self) -> RouvyDataUpdateCoordinator:
        """Return the coordinator of the loaded Rouvy entry."""
        for entry in self._hass.config_entries.async_loaded_entries(DOMAIN):
            runtime = entry.runtime_data
            if entry.state is ConfigEntryState.LOADED and isinstance(runtime, RouvyRuntimeData):
                return runtime.coordinator
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")

    @staticmethod
    async def _run[T](operation: Awaitable[T]) -> T:
        """Await a client call, translating library errors into HA errors."""
        try:
            return await operation
        except RouvyValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_request",
                translation_placeholders={"error": str(err)},
            ) from err
        except RouvyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_failed",
                translation_placeholders={"error": str(err)},
            ) from err
