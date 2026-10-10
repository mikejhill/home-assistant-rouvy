"""Tests for integration setup, unload, and coordinator refresh behaviour."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.const import DOMAIN, UPDATE_INTERVAL
from custom_components.rouvy.coordinator import RouvyRuntimeData
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import VALID_EMAIL, FakeRouvy


class TestSetup:
    """Loading and unloading config entries."""

    async def test_setup_and_unload(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """A valid entry loads, creates sensors, and unloads cleanly."""
        assert loaded_entry.state is ConfigEntryState.LOADED
        assert isinstance(loaded_entry.runtime_data, RouvyRuntimeData)
        assert len(hass.states.async_all("sensor")) > 30

        assert await hass.config_entries.async_unload(loaded_entry.entry_id)
        await hass.async_block_till_done()

        assert loaded_entry.state is ConfigEntryState.NOT_LOADED

    async def test_rejected_password_starts_reauth(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """If Rouvy rejects the stored password, setup fails and a reauth flow starts."""
        fake_rouvy.state.accounts[VALID_EMAIL] = "changed-elsewhere"
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]

    async def test_server_error_retries_setup(
        self, hass: HomeAssistant, config_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """A Rouvy outage during setup schedules a retry instead of failing permanently."""
        fake_rouvy.state.failures[Endpoint.USER_SETTINGS] = 503
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY


class TestCoordinator:
    """Periodic refreshes."""

    @staticmethod
    async def _refresh(
        hass: HomeAssistant, entry: MockConfigEntry, frozen_time: FrozenDateTimeFactory
    ) -> None:
        """Advance past the update interval and run the coordinator refresh."""
        frozen_time.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    async def test_refresh_reuses_session(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        frozen_time: FrozenDateTimeFactory,
    ) -> None:
        """A scheduled refresh does not log in again while the session is valid."""
        logins = fake_rouvy.state.login_count

        await self._refresh(hass, loaded_entry, frozen_time)

        assert fake_rouvy.state.login_count == logins

    async def test_expired_session_relogs_transparently(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        frozen_time: FrozenDateTimeFactory,
    ) -> None:
        """When Rouvy expires the session, the next refresh logs in once and stays available."""
        logins = fake_rouvy.state.login_count
        fake_rouvy.state.expire_sessions()

        await self._refresh(hass, loaded_entry, frozen_time)

        weight = hass.states.get("sensor.rouvy_weight")
        assert fake_rouvy.state.login_count == logins + 1
        assert weight is not None
        assert weight.state == "85.0"

    async def test_partial_failure_keeps_previous_values(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        frozen_time: FrozenDateTimeFactory,
    ) -> None:
        """A section that fails after a good refresh keeps its last value."""
        fake_rouvy.state.failures[Endpoint.CHALLENGES] = 500

        await self._refresh(hass, loaded_entry, frozen_time)

        challenges = hass.states.get("sensor.rouvy_active_challenges")
        assert challenges is not None
        assert challenges.state == "1"

    async def test_profile_outage_marks_everything_unavailable(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        frozen_time: FrozenDateTimeFactory,
    ) -> None:
        """If the required profile request fails, all sensors become unavailable."""
        fake_rouvy.state.failures[Endpoint.USER_SETTINGS] = 500

        await self._refresh(hass, loaded_entry, frozen_time)

        weight = hass.states.get("sensor.rouvy_weight")
        assert weight is not None
        assert weight.state == STATE_UNAVAILABLE
        assert loaded_entry.state is ConfigEntryState.LOADED
