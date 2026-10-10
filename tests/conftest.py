"""Fixtures shared by every test layer."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date

import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from rouvy_api import ClientConfig, Credentials, RouvyClient
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy
from tests.support.rouvy_payloads import RouvyPayloads


@pytest.fixture
def payloads() -> RouvyPayloads:
    """Response bodies anchored to a fixed 'today'."""
    return RouvyPayloads(today=date(2026, 10, 10))


@pytest.fixture
def fake_rouvy(payloads: RouvyPayloads) -> FakeRouvy:
    """A fake riders portal with default fixtures."""
    return FakeRouvy(payloads)


@pytest.fixture
async def fake_rouvy_server(
    fake_rouvy: FakeRouvy,
    socket_enabled: None,
) -> AsyncGenerator[TestServer]:
    """The fake portal listening on a loopback port.

    The HA test plugin blocks socket creation; ``socket_enabled`` lifts that while its
    host allow-list still limits connections to loopback.
    """
    del socket_enabled
    server = TestServer(fake_rouvy.build_app(), host="127.0.0.1")
    await server.start_server(access_log=None)
    yield server
    await server.close()


@pytest.fixture
def client_config(fake_rouvy_server: TestServer) -> ClientConfig:
    """Client settings that target the fake portal."""
    return ClientConfig(base_url=str(fake_rouvy_server.make_url("/")), timeout_s=5)


@pytest.fixture
def credentials() -> Credentials:
    """Credentials the fake portal accepts."""
    return Credentials(VALID_EMAIL, VALID_PASSWORD)


@pytest.fixture
async def rouvy_client(
    client_config: ClientConfig, credentials: Credentials
) -> AsyncGenerator[RouvyClient]:
    """A client connected to the fake portal."""
    async with aiohttp.ClientSession(cookie_jar=client_config.cookie_jar()) as session:
        yield RouvyClient(credentials, session, config=client_config)
