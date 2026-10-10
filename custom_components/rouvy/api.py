"""Construction of Rouvy clients with Home Assistant-managed HTTP sessions."""

from __future__ import annotations

from typing import ClassVar

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from custom_components.rouvy.rouvy_api import ClientConfig, Credentials, RouvyClient


class RouvyConnection:
    """A client plus the dedicated session it uses (cookies must not be shared)."""

    def __init__(self, client: RouvyClient, session: aiohttp.ClientSession) -> None:
        self._client = client
        self._session = session

    @property
    def client(self) -> RouvyClient:
        """Return the client."""
        return self._client

    def release(self) -> None:
        """Detach the session from Home Assistant's shared connector."""
        self._session.detach()


class RouvyClientFactory:
    """Create Rouvy connections; tests replace ``config`` to target a fake portal."""

    config: ClassVar[ClientConfig] = ClientConfig()

    @classmethod
    def connect(cls, hass: HomeAssistant, email: str, password: str) -> RouvyConnection:
        """Return a connection whose ``release()`` the caller must call when done."""
        session = async_create_clientsession(
            hass, auto_cleanup=False, cookie_jar=cls.config.cookie_jar()
        )
        client = RouvyClient(Credentials(email, password), session, config=cls.config)
        return RouvyConnection(client, session)
