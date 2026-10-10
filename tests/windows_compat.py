"""Pytest plugin that lets the Home Assistant test harness run on Windows.

The HA plugin blocks socket creation, but the Windows proactor event loop builds its
self-pipe from a loopback TCP socket pair. On Windows this plugin therefore turns
``disable_socket`` into a no-op; the HA plugin's host allow-list (loopback only)
still applies to every outbound connection.

Loaded with ``-p tests.windows_compat`` so it runs before the
pytest-homeassistant-custom-component plugin imports ``homeassistant.runner``,
which needs the Unix-only ``fcntl`` and ``resource`` modules. On Linux and macOS
this plugin does nothing.
"""

from __future__ import annotations

import sys
from types import ModuleType


class WindowsCompat:
    """Install stand-ins for Unix-only modules and relax socket blocking."""

    ENABLED = sys.platform == "win32"

    @classmethod
    def install_module_stubs(cls) -> None:
        """Register minimal fcntl/resource modules."""
        if not cls.ENABLED:
            return
        sys.modules.setdefault("fcntl", ModuleType("fcntl"))
        if "resource" not in sys.modules:
            resource = ModuleType("resource")
            resource.RLIMIT_NOFILE = 7  # ty: ignore[unresolved-attribute]  # stub module attribute
            resource.getrlimit = lambda _limit: (1024, 1024)  # ty: ignore[unresolved-attribute]  # stub
            resource.setrlimit = lambda _limit, _value: None  # ty: ignore[unresolved-attribute]  # stub
            sys.modules["resource"] = resource

    @classmethod
    def relax_socket_blocking(cls) -> None:
        """Keep socket creation enabled; connections stay limited to allowed hosts."""
        if not cls.ENABLED:
            return
        import pytest_socket  # noqa: PLC0415 - Windows-only patch target

        pytest_socket.disable_socket = cls._keep_sockets_enabled  # ty: ignore[invalid-assignment]  # runtime patch of a module function

    @staticmethod
    def _keep_sockets_enabled(allow_unix_socket: bool = False) -> None:  # noqa: FBT002 - mirrors pytest_socket
        """Replace pytest_socket.disable_socket on Windows."""
        del allow_unix_socket


WindowsCompat.install_module_stubs()
WindowsCompat.relax_socket_blocking()
