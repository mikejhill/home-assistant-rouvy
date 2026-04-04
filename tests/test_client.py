"""Tests for RouvyClient."""

from __future__ import annotations

import logging

import pytest
import responses

from custom_components.rouvy.api_client import (
    ApiResponseError,
    AuthenticationError,
    RouvyClient,
    RouvyConfig,
)
from custom_components.rouvy.api_client import client as client_module


def test_logger_name() -> None:
    assert client_module.LOGGER.name == "custom_components.rouvy.api_client.client"


@responses.activate
def test_login_success_sets_authenticated() -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="secret",
        )
    )

    client.login()

    assert client._authenticated is True


@responses.activate
def test_login_failure_raises_auth_error() -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    responses.add(responses.POST, auth_url, json={"ok": False}, status=401)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="secret",
        )
    )

    try:
        client.login()
        raise AssertionError("Expected AuthenticationError")
    except AuthenticationError:
        pass


@responses.activate
def test_login_success_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="super-secret-password",
        )
    )

    caplog.set_level(logging.INFO, logger="custom_components.rouvy.api_client.client")

    client.login()

    assert any(
        record.levelname == "INFO" and record.message == "Authentication successful"
        for record in caplog.records
    )


@responses.activate
def test_login_failure_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    responses.add(responses.POST, auth_url, json={"ok": False}, status=401)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="super-secret-password",
        )
    )

    caplog.set_level(logging.ERROR, logger="custom_components.rouvy.api_client.client")

    with pytest.raises(AuthenticationError):
        client.login()

    records = [
        record
        for record in caplog.records
        if record.levelname == "ERROR" and record.message == "Authentication failed"
    ]
    assert records
    assert records[0].status_code == 401


@responses.activate
def test_request_reauthenticates_on_unauthorized() -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    api_url = "https://riders.rouvy.com/user-settings.data"

    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.GET, api_url, status=401)
    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.GET, api_url, json={"ok": True}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="secret",
        )
    )

    response = client.get(api_url)

    assert response.json() == {"ok": True}
    auth_calls = [call for call in responses.calls if call.request.url == auth_url]
    assert len(auth_calls) == 2


@responses.activate
def test_get_user_settings_helper_success() -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    api_url = "https://riders.rouvy.com/user-settings.data"

    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.GET, api_url, json={"theme": "dark"}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="secret",
        )
    )

    response = client.get_user_settings()

    assert response.json() == {"theme": "dark"}


@responses.activate
def test_get_user_settings_helper_error() -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    api_url = "https://riders.rouvy.com/user-settings.data"

    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.GET, api_url, json={"error": "boom"}, status=500)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="secret",
        )
    )

    try:
        client.get_user_settings()
        raise AssertionError("Expected ApiResponseError")
    except ApiResponseError as exc:
        assert exc.status_code == 500
        assert exc.payload == {"error": "boom"}


@responses.activate
def test_request_logging_includes_context(caplog: pytest.LogCaptureFixture) -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    api_url = "https://riders.rouvy.com/user-settings.data"

    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.GET, api_url, json={"theme": "dark"}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="super-secret-password",
        )
    )

    caplog.set_level(logging.DEBUG, logger="custom_components.rouvy.api_client.client")

    response = client.get(api_url)

    assert response.json() == {"theme": "dark"}

    records = [
        record
        for record in caplog.records
        if record.message == "HTTP request completed" and record.url == api_url
    ]
    assert records
    record = records[-1]
    assert record.method == "GET"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)


@responses.activate
def test_logs_do_not_include_sensitive_data(caplog: pytest.LogCaptureFixture) -> None:
    auth_url = "https://riders.rouvy.com/login.data"
    root_url = "https://riders.rouvy.com/_root.data"
    api_url = "https://riders.rouvy.com/secure.data"

    responses.add(responses.POST, auth_url, json={"ok": True}, status=200)
    responses.add(responses.GET, root_url, json={"ok": True}, status=200)
    responses.add(responses.POST, api_url, json={"ok": True}, status=200)

    client = RouvyClient(
        RouvyConfig(
            email="user@example.com",
            password="super-secret-password",
        )
    )

    caplog.set_level(logging.DEBUG, logger="custom_components.rouvy.api_client.client")

    client.post(api_url, json={"token": "payload-secret"})

    assert "user@example.com" not in caplog.text
    assert "super-secret-password" not in caplog.text
    assert "payload-secret" not in caplog.text
