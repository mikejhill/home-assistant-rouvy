"""Custom exception classes for the Rouvy API client."""

from __future__ import annotations

from typing import Any


class RouvyApiError(Exception):
    """Base exception for all Rouvy API errors."""


class AuthenticationError(RouvyApiError):
    """Raised when authentication with Rouvy fails."""


class ApiResponseError(RouvyApiError):
    """Raised when the Rouvy API returns an error response.

    Attributes:
        status_code: HTTP status code from the response.
        payload: Parsed response body, if available.
    """

    def __init__(self, message: str, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
