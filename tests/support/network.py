"""Lift the Home Assistant test harness's network block for live tests."""

from __future__ import annotations

import socket

import pytest
import pytest_socket
from pytest_homeassistant_custom_component import plugins as ha_plugins


class RealNetwork:
    """Restore real sockets and DNS for the duration of one test."""

    @staticmethod
    def enable(monkeypatch: pytest.MonkeyPatch) -> None:
        """Undo pytest-socket and HA DNS patches; monkeypatch restores them afterwards."""
        monkeypatch.setattr(socket, "socket", pytest_socket._true_socket)
        monkeypatch.setattr(pytest_socket._true_socket, "connect", pytest_socket._true_connect)
        monkeypatch.setattr(socket, "getaddrinfo", ha_plugins._real_getaddrinfo)
        monkeypatch.setattr(socket, "gethostbyname", pytest_socket._true_gethostbyname)
