"""Fixtures for authenticated, read-only smoke tests against the real Rouvy API.

Rouvy throttles repeated logins (HTTP 429 after a few in quick succession), so the
whole module shares one logged-in client.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from rouvy_api import Credentials, RouvyClient
from tests.support.network import RealNetwork


@pytest.fixture(scope="module", autouse=True)
def real_network() -> Iterator[None]:
    """Allow real outbound connections for the whole module."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        RealNetwork.enable(monkeypatch)
        yield


@pytest.fixture(scope="module")
def live_credentials() -> Credentials:
    """Credentials from ROUVY_TEST_EMAIL / ROUVY_TEST_PASSWORD (environment or .env), or skip."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    email = os.environ.get("ROUVY_TEST_EMAIL", "")
    password = os.environ.get("ROUVY_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("Set ROUVY_TEST_EMAIL and ROUVY_TEST_PASSWORD to run live tests")
    return Credentials(email, password)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def live_client(
    real_network: None, live_credentials: Credentials
) -> AsyncGenerator[RouvyClient]:
    """One logged-in client for the test account, shared by the module."""
    del real_network
    async with RouvyClient.open(live_credentials) as client:
        await client.login()
        yield client
