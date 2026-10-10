"""Connection settings, credentials, and endpoint paths for the Rouvy client."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

import aiohttp

from rouvy_api._version import __version__

DEFAULT_BASE_URL: Final = "https://riders.rouvy.com"
PROJECT_URL: Final = "https://github.com/mikejhill/home-assistant-rouvy"
# Rouvy's firewall rejects generic library user agents (python-requests, aiohttp,
# HomeAssistant/aiohttp), so every request identifies this project explicitly.
DEFAULT_USER_AGENT: Final = f"home-assistant-rouvy/{__version__} (+{PROJECT_URL})"


class Endpoint(StrEnum):
    """Remix single-fetch data routes on the riders portal."""

    LOGIN = "login.data"
    USER_SETTINGS = "user-settings.data"
    USER_SETTINGS_ACTION = "user-settings.data?index"
    ZONES = "user-settings/zones.data"
    CONNECTED_APPS = "user-settings/connected-apps.data"
    PROFILE_OVERVIEW = "profile/overview.data"
    ACTIVITY_STATS = "resources/activity-stats.data"
    CHALLENGES = "challenges/status/available.data"
    ROUTES = "routes.data"
    FAVORITE_ROUTES = "routes/collection/favourite.data"
    EVENTS = "events.data"
    ACHIEVEMENTS = "profile/achievements.data"
    TROPHIES = "profile/trophies.data"


@dataclass(frozen=True, slots=True)
class Credentials:
    """Rouvy account credentials; the password never appears in repr()."""

    email: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        """Reject obviously unusable credentials."""
        if "@" not in self.email or not self.password:
            msg = "Credentials need an email address and a non-empty password"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Transport settings for RouvyClient."""

    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 30.0
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self) -> None:
        """Validate the base URL and timeout."""
        parts = urlsplit(self.base_url)
        if parts.scheme not in {"http", "https"} or parts.hostname in {None, ""}:
            msg = f"base_url must be an absolute http(s) URL, got {self.base_url!r}"
            raise ValueError(msg)
        if self.timeout_s <= 0:
            msg = f"timeout_s must be positive, got {self.timeout_s}"
            raise ValueError(msg)

    @property
    def host(self) -> str:
        """Return the host name of the base URL."""
        return urlsplit(self.base_url).hostname or ""

    def url(self, path: str) -> str:
        """Return the absolute URL for a relative endpoint path."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def cookie_jar(self) -> aiohttp.CookieJar:
        """Return a cookie jar that accepts this host's cookies (IP hosts need unsafe mode)."""
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            return aiohttp.CookieJar()
        return aiohttp.CookieJar(unsafe=True)
