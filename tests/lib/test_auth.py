"""Tests for HTTP response classification and login interpretation."""

from __future__ import annotations

import pytest

from rouvy_api import (
    RouvyAccountDisabledError,
    RouvyApiError,
    RouvyAuthenticationError,
    RouvyBlockedError,
    RouvyError,
    RouvyInvalidCredentialsError,
    RouvyRateLimitedError,
    RouvyResponseError,
)
from rouvy_api.auth import HttpResult, LoginResponseInterpreter, ResponseInspector
from tests.support.rouvy_payloads import RouvyPayloads

TURBO = "text/x-script"
SECRET = "s3cret-pass-value"


@pytest.fixture
def inspector() -> ResponseInspector:
    """A response inspector."""
    return ResponseInspector()


@pytest.fixture
def interpreter(inspector: ResponseInspector) -> LoginResponseInterpreter:
    """A login interpreter."""
    return LoginResponseInterpreter(inspector)


class TestResponseInspector:
    """Status handling and decoding."""

    @pytest.mark.parametrize(
        ("result", "error", "match"),
        [
            (HttpResult(403, "text/html", "<!DOCTYPE html>"), RouvyBlockedError, "firewall"),
            (HttpResult(429, TURBO, ""), RouvyRateLimitedError, "429"),
            (HttpResult(500, TURBO, ""), RouvyApiError, "server error"),
            (HttpResult(404, TURBO, ""), RouvyApiError, "HTTP 404"),
            (HttpResult(403, TURBO, "[1]"), RouvyApiError, "HTTP 403"),
        ],
    )
    def test_error_statuses(
        self,
        inspector: ResponseInspector,
        result: HttpResult,
        error: type[RouvyError],
        match: str,
    ) -> None:
        """Error statuses raise specific exceptions with the status attached."""
        with pytest.raises(error, match=match) as excinfo:
            inspector.check_status(result, context="GET x")

        assert isinstance(excinfo.value, RouvyApiError)
        assert excinfo.value.status == result.status

    def test_html_success_is_a_response_error(self, inspector: ResponseInspector) -> None:
        """A 200 HTML page where data was expected is a response error."""
        with pytest.raises(RouvyResponseError, match="HTML"):
            inspector.parse(HttpResult(200, "text/html", "<html></html>"), context="GET x")

    def test_doctype_sniffing(self) -> None:
        """HTML is detected from the body even with a wrong content type."""
        assert HttpResult(200, TURBO, "  <!DOCTYPE html>").looks_like_html

    def test_sign_in_redirect(self, inspector: ResponseInspector, payloads: RouvyPayloads) -> None:
        """Sign-in redirects are recognised; other redirects are not."""
        sign_in = inspector.parse(
            HttpResult(202, TURBO, payloads.sign_in_redirect("feed.data")), context="x"
        )
        other = inspector.parse(HttpResult(202, TURBO, payloads.redirect("/feed")), context="x")

        assert inspector.is_sign_in_redirect(sign_in)
        assert not inspector.is_sign_in_redirect(other)

    def test_unauthorized(self, inspector: ResponseInspector) -> None:
        """HTTP 401 marks an expired session."""
        assert inspector.is_unauthorized(HttpResult(401, TURBO, ""))
        assert not inspector.is_unauthorized(HttpResult(200, TURBO, ""))


class TestLoginInterpreter:
    """Login responses map to specific outcomes."""

    def test_redirect_is_success(
        self, interpreter: LoginResponseInterpreter, payloads: RouvyPayloads
    ) -> None:
        """A redirect body means the login was accepted."""
        interpreter.verify(HttpResult(202, TURBO, payloads.redirect("/")))

    @pytest.mark.parametrize(
        ("message", "error"),
        [
            ("Firebase: Error (auth/invalid-credential).", RouvyInvalidCredentialsError),
            ("Firebase: Error (auth/wrong-password).", RouvyInvalidCredentialsError),
            ("Firebase: Error (auth/user-not-found).", RouvyInvalidCredentialsError),
            ("Firebase: Error (auth/invalid-email).", RouvyInvalidCredentialsError),
            ("INVALID_LOGIN_CREDENTIALS", RouvyInvalidCredentialsError),
            ("Firebase: Error (auth/user-disabled).", RouvyAccountDisabledError),
            ("Firebase: Error (auth/too-many-requests).", RouvyRateLimitedError),
            ("Something else went wrong", RouvyAuthenticationError),
        ],
    )
    def test_form_errors(
        self,
        interpreter: LoginResponseInterpreter,
        payloads: RouvyPayloads,
        message: str,
        error: type[RouvyError],
    ) -> None:
        """Firebase codes map to exceptions that never contain the echoed password."""
        body = payloads.login_error(message, "rider@example.com", SECRET)

        with pytest.raises(error) as excinfo:
            interpreter.verify(HttpResult(200, TURBO, body))

        assert SECRET not in str(excinfo.value)

    def test_error_without_message(self, interpreter: LoginResponseInterpreter) -> None:
        """An error status with no messages still fails clearly."""
        body = RouvyPayloads.encode({"data": {"status": "error"}})

        with pytest.raises(RouvyAuthenticationError, match="without an explanation"):
            interpreter.verify(HttpResult(200, TURBO, body))

    @pytest.mark.parametrize("status", [401, 403])
    def test_rejected_status(self, interpreter: LoginResponseInterpreter, status: int) -> None:
        """Non-HTML 401/403 login responses are authentication failures."""
        with pytest.raises(RouvyAuthenticationError, match=f"HTTP {status}"):
            interpreter.verify(HttpResult(status, TURBO, "[1]"))

    def test_firewall_on_login(self, interpreter: LoginResponseInterpreter) -> None:
        """A firewall page on login is reported as blocked."""
        with pytest.raises(RouvyBlockedError):
            interpreter.verify(HttpResult(403, "text/html", "<!DOCTYPE html>"))
