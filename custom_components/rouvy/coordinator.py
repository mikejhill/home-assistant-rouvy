"""DataUpdateCoordinator for the Rouvy integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from rouvy_api_client.errors import AuthenticationError, RouvyApiError
from rouvy_api_client.models import UserProfile

from .const import DEFAULT_SCAN_INTERVAL_HOURS, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import RouvyConfigEntry


class RouvyDataUpdateCoordinator(DataUpdateCoordinator[UserProfile]):
    """Coordinator to fetch user profile data from Rouvy."""

    config_entry: RouvyConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="rouvy",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )

    async def _async_update_data(self) -> UserProfile:
        """Fetch the latest user profile from the API."""
        try:
            return await self.config_entry.runtime_data.client.async_get_user_profile()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except RouvyApiError as err:
            raise UpdateFailed(err) from err
