"""Shared fixtures for Rouvy integration tests.

⚠️  WARNING: These tests interact with the REAL Rouvy API and will
modify account settings. Use a dedicated test account only.
"""

from __future__ import annotations

import os

import aiohttp
import pytest

from custom_components.rouvy.api import RouvyAsyncApiClient


def _get_credentials() -> tuple[str, str]:
    """Read test credentials from environment variables."""
    email = os.environ.get("ROUVY_TEST_EMAIL", "")
    password = os.environ.get("ROUVY_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("ROUVY_TEST_EMAIL and ROUVY_TEST_PASSWORD not set")
    return email, password


@pytest.fixture
async def rouvy_client() -> RouvyAsyncApiClient:
    """Create an authenticated RouvyAsyncApiClient for integration testing.

    The client is created fresh for each test and the underlying session is
    closed on teardown.
    """
    email, password = _get_credentials()
    session = aiohttp.ClientSession()
    client = RouvyAsyncApiClient(email=email, password=password, session=session)
    await client.async_login()
    yield client
    await session.close()
