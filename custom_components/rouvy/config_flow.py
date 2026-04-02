"""Config flow for the Rouvy integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import RouvyAsyncApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, LOGGER


class RouvyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rouvy."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — email and password entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                valid = await self._test_credentials(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                if not valid:
                    errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                LOGGER.exception("Connection error during credential validation")
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during credential validation")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, email: str, password: str) -> bool:
        """Validate credentials by attempting to log in."""
        session = async_create_clientsession(self.hass)
        client = RouvyAsyncApiClient(
            email=email,
            password=password,
            session=session,
        )
        return await client.async_validate_credentials()
