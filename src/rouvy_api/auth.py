"""Interpretation of Rouvy login and session responses.

Rouvy's riders portal authenticates with a form POST to ``login.data``. A rejected
login is still HTTP 200: the body is a form-error payload carrying a Firebase error
code (for example ``auth/invalid-credential``). Bodies are never logged because the
error payload echoes the submitted password back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from rouvy_api.exceptions import (
    RouvyAccountDisabledError,
    RouvyApiError,
    RouvyAuthenticationError,
    RouvyBlockedError,
    RouvyInvalidCredentialsError,
    RouvyRateLimitedError,
    RouvyResponseError,
)
from rouvy_api.payload import Fields, Payload
from rouvy_api.turbo_stream import TurboValue

_INVALID_CREDENTIAL_CODES: Final = (
    "auth/invalid-credential",
    "auth/invalid-login-credentials",
    "auth/wrong-password",
    "auth/user-not-found",
    "auth/invalid-email",
    "invalid_login_credentials",
)
_SIGN_IN_MARKERS: Final = ("sign-in", "/login", "signin")
_HTTP_UNAUTHORIZED: Final = 401
_HTTP_FORBIDDEN: Final = 403
_HTTP_TOO_MANY_REQUESTS: Final = 429
_HTTP_CLIENT_ERROR: Final = 400
_HTTP_SERVER_ERROR: Final = 500


@dataclass(frozen=True, slots=True)
class HttpResult:
    """Status, content type, and text of one HTTP response."""

    status: int
    content_type: str
    text: str

    @property
    def looks_like_html(self) -> bool:
        """Return True for HTML bodies such as firewall challenge pages."""
        return "html" in self.content_type or self.text.lstrip()[:15].lower().startswith(
            "<!doctype"
        )


class ResponseInspector:
    """Classify Rouvy HTTP responses into payloads or typed errors."""

    def check_status(self, result: HttpResult, *, context: str) -> None:
        """Raise for HTTP error statuses.

        Raises:
            RouvyBlockedError: On a firewall rejection.
            RouvyRateLimitedError: On HTTP 429.
            RouvyApiError: On any other 4xx/5xx status.
        """
        if result.status < _HTTP_CLIENT_ERROR:
            return
        if result.status == _HTTP_FORBIDDEN and result.looks_like_html:
            msg = (
                f"{context}: Rouvy's firewall rejected the request (HTTP 403). "
                "This usually means Rouvy changed its bot filtering; please report it."
            )
            raise RouvyBlockedError(msg, status=result.status)
        if result.status == _HTTP_TOO_MANY_REQUESTS:
            msg = f"{context}: Rouvy is rate limiting requests (HTTP 429); try again later"
            raise RouvyRateLimitedError(msg, status=result.status)
        kind = "server error" if result.status >= _HTTP_SERVER_ERROR else "error"
        msg = f"{context}: Rouvy returned HTTP {result.status} ({kind})"
        raise RouvyApiError(msg, status=result.status)

    def parse(self, result: HttpResult, *, context: str) -> Payload:
        """Check the status and decode the turbo-stream body.

        Raises:
            RouvyResponseError: If a successful response is not turbo-stream.
        """
        self.check_status(result, context=context)
        if result.looks_like_html:
            msg = f"{context}: expected turbo-stream data but received an HTML page"
            raise RouvyResponseError(msg)
        return Payload.parse(result.text)

    @staticmethod
    def is_unauthorized(result: HttpResult) -> bool:
        """Return True when the response signals a missing or expired session."""
        return result.status == _HTTP_UNAUTHORIZED

    @staticmethod
    def is_sign_in_redirect(payload: Payload) -> bool:
        """Return True when a payload redirects to the sign-in page."""
        location = payload.redirect_location
        return location is not None and any(m in location.lower() for m in _SIGN_IN_MARKERS)


class LoginResponseInterpreter:
    """Turn a ``login.data`` response into success or a specific authentication error."""

    def __init__(self, inspector: ResponseInspector) -> None:
        self._inspector = inspector

    def verify(self, result: HttpResult) -> None:
        """Return normally when the login was accepted.

        Raises:
            RouvyInvalidCredentialsError: If the email or password is wrong.
            RouvyAccountDisabledError: If the account is disabled.
            RouvyRateLimitedError: If Rouvy is throttling logins.
            RouvyBlockedError: If the firewall rejected the request.
            RouvyAuthenticationError: For any other rejected login.
        """
        if result.status in {_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN} and not result.looks_like_html:
            msg = f"Rouvy rejected the login (HTTP {result.status})"
            raise RouvyAuthenticationError(msg)
        payload = self._inspector.parse(result, context="Login")
        data = payload.action_data
        if data is None or data.text("status") != "error":
            return
        self._raise_for_errors(self._messages(data))

    @staticmethod
    def _messages(data: Fields) -> list[str]:
        """Collect every error string from a form-error payload."""
        errors = data.raw.get("error")
        found: list[str] = []
        LoginResponseInterpreter._collect(errors, found)
        return found or ["Rouvy rejected the login without an explanation"]

    @staticmethod
    def _collect(value: TurboValue, found: list[str]) -> None:
        """Gather strings from nested lists and dicts."""
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, list):
            for item in value:
                LoginResponseInterpreter._collect(item, found)
        elif isinstance(value, dict):
            for item in value.values():
                LoginResponseInterpreter._collect(item, found)

    @staticmethod
    def _raise_for_errors(messages: list[str]) -> None:
        """Raise the most specific exception for the error messages."""
        text = "; ".join(messages)
        lowered = text.lower()
        if any(code in lowered for code in _INVALID_CREDENTIAL_CODES):
            msg = "Invalid Rouvy email or password"
            raise RouvyInvalidCredentialsError(msg)
        if "auth/user-disabled" in lowered:
            msg = "This Rouvy account is disabled"
            raise RouvyAccountDisabledError(msg)
        if "auth/too-many-requests" in lowered:
            msg = "Rouvy temporarily blocked logins after too many attempts; try again later"
            raise RouvyRateLimitedError(msg, status=None)
        msg = f"Rouvy rejected the login: {text}"
        raise RouvyAuthenticationError(msg)
