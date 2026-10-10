"""Exception hierarchy for the Rouvy API client."""

from __future__ import annotations


class RouvyError(Exception):
    """Base class for every error raised by rouvy_api."""


class RouvyConnectionError(RouvyError):
    """The Rouvy servers could not be reached or the request timed out."""


class RouvyApiError(RouvyError):
    """Rouvy answered with an unexpected HTTP status."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RouvyBlockedError(RouvyApiError):
    """The request was rejected by Rouvy's web application firewall."""


class RouvyRateLimitedError(RouvyApiError):
    """Rouvy is throttling requests from this account or address."""


class RouvyResponseError(RouvyError):
    """A response body could not be decoded or did not have the expected shape."""


class RouvyAuthenticationError(RouvyError):
    """Authentication with Rouvy failed."""


class RouvyInvalidCredentialsError(RouvyAuthenticationError):
    """Rouvy rejected the email and password combination."""


class RouvyAccountDisabledError(RouvyAuthenticationError):
    """The Rouvy account has been disabled."""


class RouvySessionError(RouvyAuthenticationError):
    """Login appeared to succeed but no usable session was established."""


class RouvyValidationError(RouvyError, ValueError):
    """A request argument was rejected before contacting Rouvy."""
