"""Tests for the Rouvy config flow: setup, errors, reauthentication, and reconfiguration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from custom_components.rouvy.rouvy_api import (
    RouvyAccountDisabledError,
    RouvyBlockedError,
    RouvyConnectionError,
    RouvyError,
    RouvyInvalidCredentialsError,
    RouvyRateLimitedError,
    RouvyResponseError,
    RouvySessionError,
)
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy

VALIDATE = "custom_components.rouvy.rouvy_api.RouvyClient.validate_credentials"


class TestUserStep:
    """The initial setup step."""

    async def test_form_is_shown_first(self, hass: HomeAssistant) -> None:
        """Starting the flow shows the credentials form without errors."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_valid_credentials_create_entry(
        self, hass: HomeAssistant, fake_rouvy: FakeRouvy
    ) -> None:
        """Valid credentials create an entry titled with the email and a lowercase unique id."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: f"  {VALID_EMAIL}  ", CONF_PASSWORD: VALID_PASSWORD},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == VALID_EMAIL
        assert result["data"] == {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
        assert result["result"].unique_id == VALID_EMAIL
        assert result["result"].state is ConfigEntryState.LOADED
        assert fake_rouvy.state.requests[0].user_agent.startswith("home-assistant-rouvy/")

    async def test_wrong_password_shows_invalid_auth_and_keeps_email(
        self, hass: HomeAssistant
    ) -> None:
        """A rejected password re-shows the form with the email pre-filled but not the password."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: "wrong"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
        schema = result["data_schema"]
        assert schema is not None
        suggested = {
            str(key): key.description.get("suggested_value")
            for key in schema.schema
            if key.description
        }
        assert suggested.get(CONF_EMAIL) == VALID_EMAIL
        assert suggested.get(CONF_PASSWORD) is None

    async def test_recovers_after_error(self, hass: HomeAssistant) -> None:
        """The user can fix a typo and finish setup in the same flow."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: "typo"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}

    async def test_session_not_started_reports_flow_change(
        self, hass: HomeAssistant, fake_rouvy: FakeRouvy
    ) -> None:
        """Accepted credentials without a session report that Rouvy's sign-in changed."""
        fake_rouvy.state.issue_session_cookie = False
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
        )

        assert result["errors"] == {"base": "auth_flow_changed"}

    async def test_disabled_account(self, hass: HomeAssistant, fake_rouvy: FakeRouvy) -> None:
        """A disabled account gets a dedicated error."""
        fake_rouvy.state.disabled_accounts.add(VALID_EMAIL)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
        )

        assert result["errors"] == {"base": "account_disabled"}

    @pytest.mark.parametrize(
        ("error", "key"),
        [
            pytest.param(RouvyInvalidCredentialsError("x"), "invalid_auth", id="invalid"),
            pytest.param(RouvyAccountDisabledError("x"), "account_disabled", id="disabled"),
            pytest.param(RouvyRateLimitedError("x"), "rate_limited", id="rate-limited"),
            pytest.param(RouvyBlockedError("x"), "blocked", id="blocked"),
            pytest.param(RouvySessionError("x"), "auth_flow_changed", id="session"),
            pytest.param(RouvyConnectionError("x"), "cannot_connect", id="connection"),
            pytest.param(RouvyResponseError("x"), "unknown", id="response"),
            pytest.param(RouvyError("x"), "unknown", id="generic"),
        ],
    )
    async def test_error_mapping(self, hass: HomeAssistant, error: RouvyError, key: str) -> None:
        """Each client error maps to a translated form error."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        with patch(VALIDATE, side_effect=error):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_EMAIL: VALID_EMAIL, CONF_PASSWORD: VALID_PASSWORD}
            )

        assert result["errors"] == {"base": key}

    async def test_invalid_email_format(self, hass: HomeAssistant) -> None:
        """An email without '@' is rejected without contacting Rouvy."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "not-an-email", CONF_PASSWORD: VALID_PASSWORD}
        )

        assert result["errors"] == {"base": "invalid_auth"}

    async def test_already_configured_aborts(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ) -> None:
        """Adding the same account twice aborts."""
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


class TestReauth:
    """Reauthentication after Rouvy rejects the stored password."""

    async def test_reauth_updates_password_and_reloads(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """Entering the new password updates the entry and reloads it."""
        fake_rouvy.state.accounts[VALID_EMAIL] = "new-password"
        result = await loaded_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"
        placeholders = result["description_placeholders"]
        assert placeholders is not None
        assert placeholders["email"] == VALID_EMAIL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert loaded_entry.data[CONF_PASSWORD] == "new-password"
        assert loaded_entry.state is ConfigEntryState.LOADED

    async def test_reauth_rejects_wrong_password(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """A wrong password keeps the reauth form open with an error."""
        result = await loaded_entry.start_reauth_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "still-wrong"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
        assert loaded_entry.data[CONF_PASSWORD] == VALID_PASSWORD


class TestReconfigure:
    """Changing the stored password proactively."""

    async def test_reconfigure_updates_password(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """A valid new password is saved and the entry reloads."""
        fake_rouvy.state.accounts[VALID_EMAIL] = "rotated"
        result = await loaded_entry.start_reconfigure_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "rotated"}
        )
        await hass.async_block_till_done()

        assert result["reason"] == "reconfigure_successful"
        assert loaded_entry.data[CONF_PASSWORD] == "rotated"

    async def test_reconfigure_error(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """A rejected password shows an error and keeps the old one."""
        result = await loaded_entry.start_reconfigure_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "nope"}
        )

        assert result["errors"] == {"base": "invalid_auth"}
        assert loaded_entry.data[CONF_PASSWORD] == VALID_PASSWORD
