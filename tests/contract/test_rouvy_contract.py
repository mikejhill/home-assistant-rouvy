"""Canary tests that detect upstream changes to Rouvy's login and data contract.

They use no account: bogus credentials and anonymous reads exercise the same code
paths as a real login. Run daily in CI so a Rouvy change is caught before users
report broken logins. Run locally with ``uv run poe contract``.
"""

from __future__ import annotations

import aiohttp
import pytest

from rouvy_api import (
    ClientConfig,
    Credentials,
    Endpoint,
    RouvyClient,
    RouvyInvalidCredentialsError,
)
from rouvy_api.auth import HttpResult, ResponseInspector

pytestmark = pytest.mark.contract
BOGUS = Credentials("contract-test@example.invalid", "definitely-not-the-password")


class TestLoginContract:
    """The login endpoint still behaves the way the client expects."""

    async def test_bogus_credentials_are_rejected_as_invalid(self) -> None:
        """Rouvy answers a wrong password with a form error the client recognises."""
        async with RouvyClient.open(BOGUS) as client:
            with pytest.raises(RouvyInvalidCredentialsError):
                await client.login()

    async def test_project_user_agent_passes_firewall(self) -> None:
        """Rouvy's firewall lets the project's user agent reach the login action."""
        config = ClientConfig()
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                config.url(Endpoint.LOGIN),
                data={"email": BOGUS.email, "password": BOGUS.password},
                headers={"User-Agent": config.user_agent},
            ) as response,
        ):
            assert response.status != 403


class TestAnonymousReads:
    """Data routes still redirect anonymous readers to sign-in."""

    @pytest.mark.parametrize(
        "endpoint",
        [Endpoint.USER_SETTINGS, Endpoint.PROFILE_OVERVIEW, Endpoint.ZONES, Endpoint.EVENTS],
    )
    async def test_data_route_redirects_to_sign_in(self, endpoint: Endpoint) -> None:
        """Anonymous single-fetch reads return a sign-in redirect the client detects."""
        config = ClientConfig()
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                config.url(endpoint),
                headers={"User-Agent": config.user_agent},
                allow_redirects=False,
            ) as response,
        ):
            result = HttpResult(response.status, response.content_type, await response.text())

        inspector = ResponseInspector()
        assert inspector.is_sign_in_redirect(inspector.parse(result, context=str(endpoint)))
