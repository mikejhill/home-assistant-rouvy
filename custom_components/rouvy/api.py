"""Async API client for the Rouvy integration.

Uses aiohttp (provided by Home Assistant) to communicate with the Rouvy API.
Reuses the turbo-stream parser and typed models from the embedded api_client
sub-package.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .api_client.errors import AuthenticationError, RouvyApiError
from .api_client.models import (
    ActivitySummary,
    ConnectedApp,
    TrainingZones,
    UserProfile,
)
from .api_client.parser import (
    extract_activities_model,
    extract_connected_apps_model,
    extract_training_zones_model,
    extract_user_profile_model,
)

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://riders.rouvy.com"


class RouvyAsyncApiClient:
    """Async HTTP client for the Rouvy API."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._email = email
        self._password = password
        self._session = session
        self._authenticated = False
        self._cookies: dict[str, str] = {}

    async def async_login(self) -> None:
        """Authenticate with Rouvy and establish a session."""
        LOGGER.debug("Starting async authentication")
        payload = {"email": self._email, "password": self._password}

        async with self._session.post(
            f"{BASE_URL}/login.data",
            data=payload,
        ) as resp:
            if resp.status >= 400:
                raise AuthenticationError(f"Login failed with status {resp.status}")
            # Capture cookies
            self._cookies.update({k: v.value for k, v in resp.cookies.items()})

        # Initialize session
        async with self._session.get(
            f"{BASE_URL}/_root.data",
            cookies=self._cookies,
        ) as resp:
            if resp.status >= 400:
                raise AuthenticationError(
                    f"Session initialization failed with status {resp.status}"
                )
            self._cookies.update({k: v.value for k, v in resp.cookies.items()})

        self._authenticated = True
        LOGGER.info("Async authentication successful")

    async def _request(self, method: str, path: str, **kwargs: Any) -> str:
        """Make an authenticated request, returning the response body text."""
        if not self._authenticated:
            await self.async_login()

        url = f"{BASE_URL}/{path.lstrip('/')}"
        kwargs.setdefault("cookies", self._cookies)

        async with self._session.request(method, url, **kwargs) as resp:
            if resp.status == 401:
                self._authenticated = False
                await self.async_login()
                kwargs["cookies"] = self._cookies
                async with self._session.request(method, url, **kwargs) as retry:
                    if retry.status >= 400:
                        raise RouvyApiError(f"Request failed with status {retry.status}")
                    return await retry.text()

            if resp.status >= 400:
                raise RouvyApiError(f"Request failed with status {resp.status}")
            return await resp.text()

    async def async_get_user_profile(self) -> UserProfile:
        """Fetch the user profile."""
        text = await self._request("GET", "user-settings.data")
        return extract_user_profile_model(text)

    async def async_get_training_zones(self) -> TrainingZones:
        """Fetch training zones."""
        text = await self._request("GET", "user-settings/zones.data")
        return extract_training_zones_model(text)

    async def async_get_connected_apps(self) -> list[ConnectedApp]:
        """Fetch connected apps."""
        text = await self._request("GET", "user-settings/connected-apps.data")
        return extract_connected_apps_model(text)

    async def async_get_activity_summary(self) -> ActivitySummary:
        """Fetch activity summary."""
        text = await self._request("GET", "profile/overview.data")
        return extract_activities_model(text)

    async def async_update_user_settings(self, updates: dict[str, Any]) -> None:
        """Update user settings (weight, height, units).

        Fetches current values first to fill required fields, then posts
        the update.
        """
        from .api_client.parser import extract_user_profile

        LOGGER.debug("Updating user settings: %s", updates)
        current_text = await self._request("GET", "user-settings.data")
        current = extract_user_profile(current_text)

        payload = {
            "height": current.get("height_cm", current.get("height", 170)),
            "weight": current.get("weight_kg", current.get("weight", 70)),
            "units": current.get("units", "METRIC"),
            "intent": "update-units",
        }
        payload.update(updates)

        await self._request(
            "POST",
            "user-settings.data?index",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        LOGGER.info("User settings updated")

    async def async_validate_credentials(self) -> bool:
        """Test that the credentials are valid. Returns True on success."""
        try:
            await self.async_login()
            return True
        except AuthenticationError:
            return False
