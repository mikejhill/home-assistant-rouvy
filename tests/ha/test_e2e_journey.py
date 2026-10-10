"""End-to-end user journey through Home Assistant against the fake Rouvy portal.

Covers onboarding, live data, an action, silent session renewal, a password change
on Rouvy's side, reauthentication, and removal — with no mocks below the HTTP layer.
"""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, UPDATE_INTERVAL
from custom_components.rouvy.coordinator import RouvyRuntimeData
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy

NEW_PASSWORD = "new-password-after-reset"


class TestUserJourney:
    """A rider's full lifecycle with the integration."""

    async def test_full_journey(
        self, hass: HomeAssistant, fake_rouvy: FakeRouvy, frozen_time: FrozenDateTimeFactory
    ) -> None:
        """Onboard, read, act, survive session expiry, reauthenticate, and remove."""
        # Onboard through the UI flow
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert entry.state is ConfigEntryState.LOADED
        runtime = entry.runtime_data
        assert isinstance(runtime, RouvyRuntimeData)
        weight = hass.states.get("sensor.rouvy_weight")
        assert weight is not None
        assert weight.state == "85.0"

        # Change weight through an action
        await hass.services.async_call(DOMAIN, "update_weight", {"weight": 79.5}, blocking=True)
        assert fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-1]["weight"] == "79.5"

        # Rouvy expires the session; the next poll renews it silently
        logins = fake_rouvy.state.login_count
        fake_rouvy.state.expire_sessions()
        frozen_time.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        await runtime.coordinator.async_refresh()
        await hass.async_block_till_done()
        assert fake_rouvy.state.login_count == logins + 1
        assert runtime.coordinator.last_update_success

        # The rider resets the password on rouvy.com; HA asks to sign in again
        fake_rouvy.state.accounts[VALID_EMAIL] = NEW_PASSWORD
        fake_rouvy.state.expire_sessions()
        await runtime.coordinator.async_refresh()
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]

        # Complete reauthentication; the entry reloads with fresh data
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
        )
        await hass.async_block_till_done()
        assert result["reason"] == "reauth_successful"
        assert entry.state is ConfigEntryState.LOADED
        assert entry.data[CONF_PASSWORD] == NEW_PASSWORD
        next_event = hass.states.get("sensor.rouvy_next_event")
        assert next_event is not None
        assert next_event.state == "Saturday Morning Ride"

        # Remove the integration
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.rouvy_weight") is None
        assert all(
            r.user_agent.startswith("home-assistant-rouvy/") for r in fake_rouvy.state.requests
        )
