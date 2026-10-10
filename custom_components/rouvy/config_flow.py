"""Config flow for the Rouvy integration: setup, reauthentication, and reconfiguration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, override

import probatio as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from custom_components.rouvy.api import RouvyClientFactory
from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, LOGGER
from custom_components.rouvy.rouvy_api import (
    RouvyAccountDisabledError,
    RouvyAuthenticationError,
    RouvyBlockedError,
    RouvyConnectionError,
    RouvyError,
    RouvyInvalidCredentialsError,
    RouvyRateLimitedError,
)

_EMAIL_SELECTOR: Final = TextSelector(
    TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
)
_PASSWORD_SELECTOR: Final = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)
# Most specific first: each error class maps to a translated form error
_ERROR_KEYS: Final[tuple[tuple[type[RouvyError], str], ...]] = (
    (RouvyInvalidCredentialsError, "invalid_auth"),
    (RouvyAccountDisabledError, "account_disabled"),
    (RouvyRateLimitedError, "rate_limited"),
    (RouvyBlockedError, "blocked"),
    (RouvyAuthenticationError, "auth_flow_changed"),
    (RouvyConnectionError, "cannot_connect"),
)


class RouvyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rouvy."""

    VERSION = 1

    @override
    async def async_step_user(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Ask for the account email and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): _EMAIL_SELECTOR,
                vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_EMAIL: user_input[CONF_EMAIL]} if user_input is not None else {}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, str]) -> ConfigFlowResult:  # noqa: ARG002 - HA signature
        """Start reauthentication after Rouvy rejected the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password for the existing account."""
        entry = self._get_reauth_entry()
        email = entry.data[CONF_EMAIL]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}),
            description_placeholders={"email": email},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Let the user update the stored password of the same account."""
        entry = self._get_reconfigure_entry()
        email = entry.data[CONF_EMAIL]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}),
            description_placeholders={"email": email},
            errors=errors,
        )

    async def _validate(self, email: str, password: str) -> dict[str, str]:
        """Log in with the credentials and return form errors (empty on success)."""
        try:
            connection = RouvyClientFactory.connect(self.hass, email, password)
        except ValueError:
            return {"base": "invalid_auth"}
        try:
            await connection.client.validate_credentials()
        except RouvyError as err:
            return {"base": self._error_key(err)}
        finally:
            connection.release()
        return {}

    @staticmethod
    def _error_key(err: RouvyError) -> str:
        """Map a client error to a translated form error key."""
        for error_type, key in _ERROR_KEYS:
            if isinstance(err, error_type):
                return key
        LOGGER.exception("Unexpected error validating Rouvy credentials", exc_info=err)
        return "unknown"
