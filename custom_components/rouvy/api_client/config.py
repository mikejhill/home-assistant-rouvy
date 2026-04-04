"""Configuration dataclass for the Rouvy API client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouvyConfig:
    """Credentials and settings for connecting to the Rouvy API.

    Attributes:
        email: Login email address.
        password: Login password.
        timeout_seconds: HTTP request timeout in seconds.
    """

    email: str
    password: str
    timeout_seconds: float = 30.0
