"""Async API client for the Rouvy integration.

Uses aiohttp (provided by Home Assistant) to communicate with the Rouvy API.
Reuses the turbo-stream parser and typed models from the embedded api_client
sub-package.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .api_client.errors import AuthenticationError, RouvyApiError
from .api_client.models import (
    ActivitySummary,
    CareerStats,
    Challenge,
    ConnectedApp,
    Event,
    FriendsSummary,
    Route,
    TrainingZones,
    UserProfile,
    WeeklyActivityStats,
)
from .api_client.parser import (
    extract_activities_model,
    extract_activity_stats_model,
    extract_career_model,
    extract_challenges_model,
    extract_connected_apps_model,
    extract_events_model,
    extract_friends_model,
    extract_routes_model,
    extract_training_zones_model,
    extract_user_profile_model,
)

_LOGGER = logging.getLogger(__name__)
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
        _LOGGER.debug("Starting async authentication for %s", self._email)
        self._cookies.clear()
        payload = {"email": self._email, "password": self._password}

        async with self._session.post(
            f"{BASE_URL}/login.data",
            data=payload,
        ) as resp:
            _LOGGER.debug(
                "Login response: status=%s",
                resp.status,
            )
            if resp.status >= 400:
                raise AuthenticationError(f"Login failed with status {resp.status}")
            self._cookies.update({k: v.value for k, v in resp.cookies.items()})

        # Initialize session via _root.data
        async with self._session.get(
            f"{BASE_URL}/_root.data",
            cookies=self._cookies,
        ) as resp:
            _LOGGER.debug(
                "Session init (_root.data) response: status=%s",
                resp.status,
            )
            if resp.status >= 400:
                raise AuthenticationError(
                    f"Session initialization failed with status {resp.status}"
                )
            self._cookies.update({k: v.value for k, v in resp.cookies.items()})

        self._authenticated = True
        _LOGGER.info("Async authentication successful for %s", self._email)

    async def _request(self, method: str, path: str, **kwargs: Any) -> str:
        """Make an authenticated request, returning the response body text.

        Handles 401 (session expired) and 202 redirect (incomplete auth)
        by re-authenticating and retrying once.
        """
        if not self._authenticated:
            _LOGGER.debug("Not authenticated, logging in before request")
            await self.async_login()

        url = f"{BASE_URL}/{path.lstrip('/')}"
        kwargs.setdefault("cookies", self._cookies)

        start = time.monotonic()
        async with self._session.request(method, url, **kwargs) as resp:
            elapsed_ms = (time.monotonic() - start) * 1000
            _LOGGER.debug(
                "HTTP %s %s -> %s (%.0fms)",
                method,
                path,
                resp.status,
                elapsed_ms,
            )

            # 401 Unauthorized — session expired, re-auth and retry
            if resp.status == 401:
                _LOGGER.info("Got 401 on %s %s, re-authenticating", method, path)
                self._authenticated = False
                await self.async_login()
                kwargs["cookies"] = self._cookies
                return await self._retry_request(method, url, path, **kwargs)

            # 202 with redirect payload — incomplete auth state
            if resp.status == 202:
                body = await resp.text()
                if self._is_redirect_body(body):
                    _LOGGER.info(
                        "Got 202 redirect on %s %s, re-initializing session",
                        method,
                        path,
                    )
                    self._authenticated = False
                    await self.async_login()
                    kwargs["cookies"] = self._cookies
                    return await self._retry_request(method, url, path, **kwargs)

            if resp.status >= 400:
                body = await resp.text()
                _LOGGER.error(
                    "Request failed: %s %s -> %s, body=%s",
                    method,
                    path,
                    resp.status,
                    body[:200],
                )
                raise RouvyApiError(f"Request {method} {path} failed with status {resp.status}")

            return await resp.text()

    async def _retry_request(self, method: str, url: str, path: str, **kwargs: Any) -> str:
        """Retry a request once after re-authentication."""
        start = time.monotonic()
        async with self._session.request(method, url, **kwargs) as retry:
            elapsed_ms = (time.monotonic() - start) * 1000
            _LOGGER.debug(
                "HTTP %s %s (retry) -> %s (%.0fms)",
                method,
                path,
                retry.status,
                elapsed_ms,
            )
            if retry.status >= 400:
                body = await retry.text()
                _LOGGER.error(
                    "Retry failed: %s %s -> %s, body=%s",
                    method,
                    path,
                    retry.status,
                    body[:200],
                )
                raise RouvyApiError(
                    f"Request {method} {path} failed with status {retry.status} after re-auth"
                )
            return await retry.text()

    @staticmethod
    def _is_redirect_body(body: str) -> bool:
        """Check if a response body is a SingleFetchRedirect (incomplete auth)."""
        try:
            import json

            data = json.loads(body)
            if isinstance(data, list) and len(data) > 0:
                return bool(data[0] == ["SingleFetchRedirect", 1])
        except ValueError, TypeError, IndexError:
            pass
        return False

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

    async def async_get_activity_stats(self, year: int, month: int) -> list[WeeklyActivityStats]:
        """Fetch weekly activity statistics for a given month.

        Args:
            year: Calendar year (e.g., 2026).
            month: Calendar month (1-12).

        Returns:
            List of WeeklyActivityStats for the weeks in that month.
        """
        text = await self._request(
            "POST",
            "resources/activity-stats.data",
            data={"year": str(year), "month": str(month)},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        return extract_activity_stats_model(text)

    async def async_get_friends(self) -> FriendsSummary:
        """Fetch friends summary."""
        text = await self._request("GET", "friends.data")
        return extract_friends_model(text)

    async def async_get_challenges(self) -> list[Challenge]:
        """Fetch available challenges."""
        text = await self._request("GET", "challenges/status/available.data")
        return extract_challenges_model(text)

    async def async_get_career(self) -> CareerStats:
        """Fetch career progression stats."""
        text = await self._request("GET", "profile/career.data")
        return extract_career_model(text)

    async def async_register_challenge(self, slug: str) -> bool:
        """Register for a challenge by slug. Returns True on success."""
        import json as _json

        text = await self._request(
            "POST",
            f"challenges/{slug}.data",
            data={"intent": "register"},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        try:
            result = _json.loads(text)
            if isinstance(result, dict):
                return bool(result.get("ok", False))
        except ValueError, TypeError:
            pass
        return False

    async def async_update_user_settings(self, updates: dict[str, Any]) -> None:
        """Update weight, height, and/or units (intent=update-units).

        Fetches current values first to fill required fields, then posts
        the update.  Supported fields:

        - ``weight`` — body weight (kg)
        - ``height`` — body height (cm)
        - ``units`` — "METRIC" or "IMPERIAL"

        Args:
            updates: Dict of field names to new values.
        """
        from .api_client.parser import extract_user_profile

        _LOGGER.debug("Updating user settings: %s", updates)
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
        _LOGGER.info("User settings updated")

    async def async_update_user_profile(self, updates: dict[str, Any]) -> None:
        """Update profile identity fields (intent=update-profile).

        Fetches current values first to populate required fields.  Supported:

        - ``username`` / ``userName`` — display username
        - ``firstName`` — first name
        - ``lastName`` — last name
        - ``gender`` — "MALE" or "FEMALE"
        - ``dateOfBirth`` — ISO date string (YYYY-MM-DD)
        - ``countryIsoCode`` — two-letter country code
        - ``team`` — team name

        The Rouvy API requires ``countryIsoCode``, ``gender``, and
        ``dateOfBirth`` on every profile update.  If the current profile
        does not have them and the caller does not supply them, sensible
        defaults are used.

        Args:
            updates: Dict of field names to new values.
        """
        from .api_client.parser import extract_user_profile

        _LOGGER.debug("Updating user profile: %s", updates)
        current_text = await self._request("GET", "user-settings.data")
        current = extract_user_profile(current_text)

        # Map convenience keys to API field names
        if "userName" in updates:
            updates["username"] = updates.pop("userName")

        # Build full payload — Rouvy requires all profile fields
        payload: dict[str, Any] = {
            "currentUsername": current.get("username", ""),
            "username": current.get("username", ""),
            "firstName": current.get("first_name", ""),
            "lastName": current.get("last_name", ""),
            "gender": current.get("gender") or "MALE",
            "dateOfBirth": current.get("birth_date") or "2000-01-01",
            "countryIsoCode": current.get("country") or "US",
            "team": current.get("team", ""),
            "intent": "update-profile",
        }

        # Apply user updates (these always take precedence)
        payload.update(updates)

        _LOGGER.debug("Profile update payload: %s", payload)
        await self._request(
            "POST",
            "user-settings.data?index",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("User profile updated")

    async def async_update_user_social(self, privacy: str) -> None:
        """Update account privacy (intent=update-social).

        Args:
            privacy: "PUBLIC" or "PRIVATE".
        """
        _LOGGER.debug("Updating account privacy to %s", privacy)
        await self._request(
            "POST",
            "user-settings.data?index",
            data={"privacy": privacy, "intent": "update-social"},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("Account privacy updated to %s", privacy)

    async def async_update_timezone(self, timezone: str) -> None:
        """Update the user's timezone.

        Args:
            timezone: IANA timezone string (e.g. "America/New_York").
        """
        _LOGGER.debug("Updating timezone to %s", timezone)
        await self._request(
            "POST",
            "resources/timezone.data",
            data={"timezone": timezone, "intent": "update-timezone"},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("Timezone updated to %s", timezone)

    async def async_update_ftp(self, ftp_source: str, value: int | None = None) -> None:
        """Update FTP (Functional Threshold Power) source and value.

        Fetches current zones first to preserve zone boundaries and get the
        old FTP value, then posts the update.

        Args:
            ftp_source: FTP source — "MANUAL" or "ESTIMATED".
            value: New FTP in watts (required when ftp_source is "MANUAL").
        """
        _LOGGER.debug("Updating FTP: source=%s, value=%s", ftp_source, value)
        current = await self.async_get_training_zones()

        zones_str = "[" + ",".join(str(v) for v in current.power_zone_values) + "]"
        payload: dict[str, Any] = {
            "type": "power",
            "ftpSource": ftp_source,
            "oldValue": current.ftp_watts,
            "zones": zones_str,
        }
        if ftp_source == "MANUAL":
            if value is None:
                msg = "value is required when ftp_source is MANUAL"
                raise ValueError(msg)
            payload["value"] = value

        await self._request(
            "POST",
            "user-settings/zones.data",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("FTP updated: source=%s, value=%s", ftp_source, value)

    async def async_update_zones(self, zone_type: str, zones: list[int]) -> None:
        """Update training zone boundaries.

        Fetches current zones and user settings first to preserve the
        reference value (FTP for power, maxHR for heartRate), then posts
        the updated zone boundaries.

        Args:
            zone_type: Zone type — "power" or "heartRate".
            zones: List of zone boundary percentages
                (e.g. [55, 75, 90, 105, 120, 150]).
        """
        from .api_client.parser import extract_user_profile

        _LOGGER.debug("Updating %s zones: %s", zone_type, zones)
        current = await self.async_get_training_zones()

        zones_str = "[" + ",".join(str(v) for v in zones) + "]"
        payload: dict[str, Any] = {"type": zone_type, "zones": zones_str}

        if zone_type == "heartRate":
            payload["oldValue"] = current.max_heart_rate
            payload["value"] = current.max_heart_rate
        else:
            settings_text = await self._request("GET", "user-settings.data")
            settings = extract_user_profile(settings_text)
            ftp_source = settings.get("ftp_source", "ESTIMATED")
            payload["ftpSource"] = ftp_source
            payload["oldValue"] = current.ftp_watts
            if ftp_source == "MANUAL":
                payload["value"] = current.ftp_watts

        await self._request(
            "POST",
            "user-settings/zones.data",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("%s zones updated", zone_type)

    async def async_update_max_heart_rate(self, max_hr: int) -> None:
        """Update maximum heart rate.

        Uses the heart rate zone endpoint to update the max HR value
        while preserving current zone boundaries.

        Args:
            max_hr: Maximum heart rate in bpm.
        """
        _LOGGER.debug("Updating max heart rate to %d", max_hr)
        current = await self.async_get_training_zones()

        # Use custom values if set, otherwise fall back to defaults
        hr_zones = current.hr_zone_values or current.hr_zone_defaults
        zones_str = "[" + ",".join(str(v) for v in hr_zones) + "]"
        payload: dict[str, Any] = {
            "type": "heartRate",
            "oldValue": current.max_heart_rate,
            "value": max_hr,
            "zones": zones_str,
        }

        await self._request(
            "POST",
            "user-settings/zones.data",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        _LOGGER.info("Max heart rate updated to %d", max_hr)

    async def async_get_favorite_routes(self) -> list[Route]:
        """Fetch routes and return only favorites."""
        text = await self._request("GET", "routes.data")
        all_routes = extract_routes_model(text)
        return [r for r in all_routes if r.favorite]

    async def async_get_events(self) -> list[Event]:
        """Fetch upcoming events."""
        text = await self._request("GET", "events.data")
        return extract_events_model(text)

    async def async_register_event(self, event_id: str) -> bool:
        """Register for an event by ID. Returns True on success."""
        import json as _json

        text = await self._request(
            "POST",
            f"events/{event_id}.data",
            data={"eventId": event_id, "intent": "register"},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        try:
            result = _json.loads(text)
            if isinstance(result, dict):
                return bool(result.get("registered", False))
        except ValueError, TypeError:
            pass
        return False

    async def async_unregister_event(self, event_id: str) -> bool:
        """Unregister from an event by ID. Returns True on success."""
        import json as _json

        text = await self._request(
            "POST",
            f"events/{event_id}.data",
            data={"eventId": event_id, "intent": "unregister"},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        try:
            result = _json.loads(text)
            if isinstance(result, dict):
                return not bool(result.get("registered", True))
        except ValueError, TypeError:
            pass
        return False

    async def async_validate_credentials(self) -> bool:
        """Test that the credentials are valid. Returns True on success."""
        try:
            await self.async_login()
            return True
        except AuthenticationError:
            return False
