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
            self._consecutive_auth_failures = 0
            _LOGGER.debug("Coordinator update successful")
            return RouvyCoordinatorData(profile=profile)
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
