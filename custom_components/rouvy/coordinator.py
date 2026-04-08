"""DataUpdateCoordinator for the Rouvy integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api_client.errors import AuthenticationError, RouvyApiError
from .api_client.models import RouvyCoordinatorData
from .const import DEFAULT_SCAN_INTERVAL_HOURS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import RouvyConfigEntry

_LOGGER = logging.getLogger(__name__)


class RouvyDataUpdateCoordinator(DataUpdateCoordinator[RouvyCoordinatorData]):
    """Coordinator to fetch data from Rouvy."""

    config_entry: RouvyConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RouvyConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="rouvy",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self._consecutive_auth_failures = 0

    async def _async_update_data(self) -> RouvyCoordinatorData:
        """Fetch the latest data from the API.

        Session expiry is expected — the client handles re-auth automatically.
        Only escalate to ConfigEntryAuthFailed after multiple consecutive auth
        failures, which indicates the credentials themselves are invalid.
        """
        client = self.config_entry.runtime_data.client
        try:
            profile = await client.async_get_user_profile()

            # Fetch activity stats for the current month
            activity_stats: list = []
            try:
                from datetime import datetime

                now = datetime.now()
                activity_stats = await client.async_get_activity_stats(now.year, now.month)
            except Exception:
                _LOGGER.debug("Failed to fetch activity stats, continuing without", exc_info=True)

            # Fetch challenges
            challenges: list = []
            try:
                challenges = await client.async_get_challenges()
            except Exception:
                _LOGGER.debug("Failed to fetch challenges, continuing without", exc_info=True)

            # Fetch training zones
            training_zones = None
            try:
                training_zones = await client.async_get_training_zones()
            except Exception:
                _LOGGER.debug("Failed to fetch training zones, continuing without", exc_info=True)

            # Fetch connected apps
            connected_apps: list = []
            try:
                connected_apps = await client.async_get_connected_apps()
            except Exception:
                _LOGGER.debug("Failed to fetch connected apps, continuing without", exc_info=True)

            # Fetch activity summary
            activity_summary = None
            try:
                activity_summary = await client.async_get_activity_summary()
            except Exception:
                _LOGGER.debug("Failed to fetch activity summary, continuing without", exc_info=True)

            # Fetch favorite routes
            favorite_routes: list = []
            try:
                favorite_routes = await client.async_get_favorite_routes()
            except Exception:
                _LOGGER.debug("Failed to fetch favorite routes, continuing without", exc_info=True)

            # Fetch upcoming events
            upcoming_events: list = []
            try:
                upcoming_events = await client.async_get_events()
            except Exception:
                _LOGGER.debug("Failed to fetch events, continuing without", exc_info=True)

            # Fetch career stats
            career = None
            try:
                career = await client.async_get_career()
            except Exception:
                _LOGGER.debug("Failed to fetch career stats, continuing without", exc_info=True)

            # Fetch achievements summary
            achievements = None
            try:
                achievements = await client.async_get_achievements()
            except Exception:
                _LOGGER.debug("Failed to fetch achievements, continuing without", exc_info=True)

            # Fetch trophies summary
            trophies = None
            try:
                trophies = await client.async_get_trophies()
            except Exception:
                _LOGGER.debug("Failed to fetch trophies, continuing without", exc_info=True)

            # Fetch friends summary
            friends = None
            try:
                friends = await client.async_get_friends()
            except Exception:
                _LOGGER.debug("Failed to fetch friends, continuing without", exc_info=True)

            self._consecutive_auth_failures = 0
            _LOGGER.debug("Coordinator update successful")
            return RouvyCoordinatorData(
                profile=profile,
                activity_stats=activity_stats,
                challenges=challenges,
                training_zones=training_zones,
                connected_apps=connected_apps,
                activity_summary=activity_summary,
                favorite_routes=favorite_routes,
                upcoming_events=upcoming_events,
                career=career,
                achievements=achievements,
                trophies=trophies,
                friends=friends,
            )
        except AuthenticationError as err:
            self._consecutive_auth_failures += 1
            _LOGGER.warning(
                "Authentication failed during update (attempt %d): %s",
                self._consecutive_auth_failures,
                err,
            )
            if self._consecutive_auth_failures >= 3:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed {self._consecutive_auth_failures} consecutive "
                    f"times — credentials may be invalid: {err}"
                ) from err
            raise UpdateFailed(
                f"Authentication failed (attempt {self._consecutive_auth_failures}/3, "
                f"will retry): {err}"
            ) from err
        except RouvyApiError as err:
            _LOGGER.warning("API error during update: %s", err)
            raise UpdateFailed(err) from err
