"""Shared fixtures for Rouvy integration tests.

⚠️  WARNING: These tests interact with the REAL Rouvy API and will
modify account settings. Settings are restored on a best-effort basis.
"""

from __future__ import annotations

import os

import aiohttp
import pytest
from dotenv import load_dotenv

from custom_components.rouvy.api import RouvyAsyncApiClient

load_dotenv()

# Cache auth cookies to avoid repeated logins (prevents 429 rate limiting).
# Each test still gets its own aiohttp session (required by pytest-asyncio
# function-scoped event loops) but skips the login round-trip.
_cached_cookies: dict[str, str] | None = None


def _get_credentials() -> tuple[str, str]:
    """Read test credentials from environment variables."""
    email = os.environ.get("ROUVY_TEST_EMAIL", "")
    password = os.environ.get("ROUVY_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("ROUVY_TEST_EMAIL and ROUVY_TEST_PASSWORD not set")
    return email, password


@pytest.fixture(autouse=True)
def _enable_real_sockets(socket_enabled):
    """Allow real network connections for integration tests."""


@pytest.fixture
async def rouvy_client() -> RouvyAsyncApiClient:
    """Provide an authenticated RouvyAsyncApiClient for integration testing.

    Caches authentication cookies across tests to avoid 429 rate-limit errors
    from repeated logins. Each test gets a fresh aiohttp session to avoid
    event-loop conflicts with pytest-asyncio.
    """
    global _cached_cookies

    email, password = _get_credentials()
    session = aiohttp.ClientSession()
    client = RouvyAsyncApiClient(email=email, password=password, session=session)

    if _cached_cookies:
        # Inject cached cookies to skip login
        client._cookies.update(_cached_cookies)
        client._authenticated = True
    else:
        await client.async_login()
        _cached_cookies = dict(client._cookies)

    yield client
    # Update cache with any refreshed cookies
    _cached_cookies = dict(client._cookies)
    await session.close()
