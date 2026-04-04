"""Pytest configuration for the rouvy-api test suite."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

# Add project root to sys.path so custom_components can be imported in tests.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Mock homeassistant modules so custom_components.rouvy can be imported
# without a real Home Assistant installation.
# ---------------------------------------------------------------------------
_HA_MODULES = [
    "homeassistant",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.exceptions",
    "homeassistant.loader",
]
for _mod in _HA_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = ModuleType(_mod)

# Populate commonly referenced attributes on the mock modules
_const = sys.modules["homeassistant.const"]
for _attr in (
    "Platform",
    "UnitOfLength",
    "UnitOfMass",
    "UnitOfPower",
    "CONF_EMAIL",
    "CONF_PASSWORD",
):
    setattr(_const, _attr, MagicMock())

_core = sys.modules["homeassistant.core"]
for _attr in ("HomeAssistant", "ServiceCall"):
    setattr(_core, _attr, MagicMock())

_config_entries = sys.modules["homeassistant.config_entries"]
_config_entries.ConfigEntry = MagicMock()
_config_entries.ConfigFlow = MagicMock()

_update_coord = sys.modules["homeassistant.helpers.update_coordinator"]
_update_coord.DataUpdateCoordinator = MagicMock()
_update_coord.UpdateFailed = type("UpdateFailed", (Exception,), {})

_entity_platform = sys.modules["homeassistant.helpers.entity_platform"]
_entity_platform.AddEntitiesCallback = MagicMock()

_device_registry = sys.modules["homeassistant.helpers.device_registry"]
_device_registry.DeviceEntryType = MagicMock()
_device_registry.DeviceInfo = MagicMock()

_aiohttp_client = sys.modules["homeassistant.helpers.aiohttp_client"]
_aiohttp_client.async_get_clientsession = MagicMock()

_sensor = sys.modules["homeassistant.components.sensor"]
for _attr in ("SensorDeviceClass", "SensorEntity", "SensorEntityDescription", "SensorStateClass"):
    setattr(_sensor, _attr, MagicMock())

_exceptions = sys.modules["homeassistant.exceptions"]
_exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})

_loader = sys.modules["homeassistant.loader"]
_loader.async_get_loaded_integration = MagicMock()
_loader.Integration = MagicMock()
