"""Tests for custom exception classes."""

import pytest

from rouvy_api_client.errors import ApiResponseError, AuthenticationError, RouvyApiError


class TestRouvyApiError:
    """Verify base error class behavior."""

    def test_is_exception(self) -> None:
        err = RouvyApiError("something broke")
        assert isinstance(err, Exception), (
            f"Expected RouvyApiError to be an Exception, got {type(err).__mro__}"
        )

    def test_message_accessible(self) -> None:
        err = RouvyApiError("something broke")
        assert str(err) == "something broke", f"Expected message 'something broke', got '{err}'"


class TestAuthenticationError:
    """Verify auth error inherits from RouvyApiError."""

    def test_inherits_rouvy_api_error(self) -> None:
        err = AuthenticationError("bad credentials")
        assert isinstance(err, RouvyApiError), (
            "Expected AuthenticationError to inherit from RouvyApiError"
        )

    def test_catchable_as_base(self) -> None:
        with pytest.raises(RouvyApiError):
            raise AuthenticationError("auth failed")

    def test_message_accessible(self) -> None:
        err = AuthenticationError("auth failed")
        assert str(err) == "auth failed", f"Expected message 'auth failed', got '{err}'"


class TestApiResponseError:
    """Verify API response error with status code and payload."""

    def test_status_code_stored(self) -> None:
        err = ApiResponseError("error", status_code=404)
        assert err.status_code == 404, f"Expected status_code 404, got {err.status_code}"

    def test_payload_stored(self) -> None:
        payload = {"detail": "not found"}
        err = ApiResponseError("error", status_code=404, payload=payload)
        assert err.payload == {"detail": "not found"}, f"Expected payload dict, got {err.payload}"

    def test_payload_defaults_to_none(self) -> None:
        err = ApiResponseError("error", status_code=500)
        assert err.payload is None, f"Expected None default payload, got {err.payload}"

    def test_inherits_rouvy_api_error(self) -> None:
        err = ApiResponseError("error", status_code=500)
        assert isinstance(err, RouvyApiError), (
            "Expected ApiResponseError to inherit from RouvyApiError"
        )

    def test_message_accessible(self) -> None:
        err = ApiResponseError("request failed", status_code=500)
        assert str(err) == "request failed", f"Expected message 'request failed', got '{err}'"

    def test_payload_with_string(self) -> None:
        err = ApiResponseError("error", status_code=502, payload="gateway error")
        assert err.payload == "gateway error", f"Expected string payload, got {err.payload}"

    def test_payload_with_list(self) -> None:
        err = ApiResponseError("error", status_code=400, payload=["field1", "field2"])
        assert err.payload == ["field1", "field2"], f"Expected list payload, got {err.payload}"
