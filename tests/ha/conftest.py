"""Fixtures for Home Assistant integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.api import RouvyClientFactory
from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from custom_components.rouvy.rouvy_api import ClientConfig
from rouvy_api import ClientConfig as LibraryClientConfig
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD

FROZEN_NOW = "2026-10-10T12:00:00+00:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/rouvy in every HA test."""


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Pin 'now' to the date the synthetic payloads are anchored to."""
    freezer.move_to(FROZEN_NOW)
    return freezer


@pytest.fixture(autouse=True)
def portal(client_config: LibraryClientConfig) -> Iterator[ClientConfig]:
    """Point the integration's client factory at the fake portal."""
    original = RouvyClientFactory.config
    RouvyClientFactory.config = ClientConfig(
        base_url=client_config.base_url, timeout_s=client_config.timeout_s
    )
    yield RouvyClientFactory.config
    RouvyClientFactory.config = original


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry for the fake account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=VALID_EMAIL,
        unique_id=VALID_EMAIL,
        data={CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD},
    )


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    """The config entry, set up and loaded."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
