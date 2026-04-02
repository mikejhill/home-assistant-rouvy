"""Custom type definitions for the Rouvy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.loader import Integration

if TYPE_CHECKING:
    from .api import RouvyAsyncApiClient
    from .coordinator import RouvyDataUpdateCoordinator

type RouvyConfigEntry = ConfigEntry[RouvyData]


@dataclass
class RouvyData:
    """Runtime data for a Rouvy config entry."""

    client: RouvyAsyncApiClient
    coordinator: RouvyDataUpdateCoordinator
    integration: Integration
