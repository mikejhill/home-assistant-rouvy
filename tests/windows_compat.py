"""Pytest plugin: mock Unix-only modules for Windows compatibility.

Registered via pyproject.toml addopts as ``-p tests.windows_compat`` so it
loads before the pytest-homeassistant-custom-component entry-point plugin,
which transitively imports ``homeassistant.runner`` (depends on fcntl/resource).

On Linux/macOS these modules already exist and this plugin is a no-op.
"""

from __future__ import annotations

import platform
import sys
from types import ModuleType

_IS_WINDOWS = platform.system() == "Windows"

# Mock Unix-only modules that homeassistant.runner imports.
for _mod_name in ("fcntl", "resource"):
    if _mod_name not in sys.modules:
        _m = ModuleType(_mod_name)
        if _mod_name == "resource":
            _m.RLIMIT_NOFILE = 7  # type: ignore[attr-defined]
            _m.getrlimit = lambda x: (1024, 1024)  # type: ignore[attr-defined]
            _m.setrlimit = lambda x, y: None  # type: ignore[attr-defined]
        sys.modules[_mod_name] = _m


if _IS_WINDOWS:
    import pytest_socket

    def pytest_runtest_setup() -> None:
        """Re-enable localhost sockets on Windows after HA plugin disables them.

        The HA test framework calls ``disable_socket(allow_unix_socket=True)``
        which works on Linux (asyncio uses AF_UNIX socketpair) but breaks on
        Windows where asyncio ProactorEventLoop uses AF_INET socketpair on
        127.0.0.1. We allow all hosts so the event loop can function.
        """
        pytest_socket.socket_allow_hosts(allowed=None)
        pytest_socket.enable_socket()
