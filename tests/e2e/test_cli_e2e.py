"""End-to-end tests: the CLI as a real subprocess against the fake Rouvy portal."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from rouvy_api import ClientConfig
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy


class CliProcess:
    """Run ``python -m rouvy_api.cli`` and capture the result."""

    def __init__(self, base_url: str, cwd: Path) -> None:
        self._cwd = cwd
        self._env = {
            **os.environ,
            "ROUVY_EMAIL": VALID_EMAIL,
            "ROUVY_PASSWORD": VALID_PASSWORD,
            "ROUVY_BASE_URL": base_url,
            "PYTHONIOENCODING": "utf-8",
        }

    async def run(self, *argv: str, password: str | None = None) -> tuple[int, str, str]:
        """Return exit status, stdout, and stderr."""
        env = dict(self._env)
        if password is not None:
            env["ROUVY_PASSWORD"] = password
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "rouvy_api.cli",
            *argv,
            cwd=self._cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        return process.returncode or 0, stdout.decode(), stderr.decode()


@pytest.fixture
def cli(client_config: ClientConfig, tmp_path: Path) -> CliProcess:
    """A CLI runner in an empty directory pointed at the fake portal."""
    return CliProcess(client_config.base_url, tmp_path)


class TestCliProcess:
    """The installed entry point works end to end."""

    async def test_login_check(self, cli: CliProcess) -> None:
        """login-check succeeds with valid credentials."""
        code, out, err = await cli.run("login-check")

        assert code == 0, err
        assert out.strip() == f"Logged in as {VALID_EMAIL} (test-rider)"

    async def test_profile_json(self, cli: CliProcess) -> None:
        """Profile --json prints the parsed profile."""
        code, out, _ = await cli.run("--json", "profile")

        assert code == 0
        assert json.loads(out)["max_heart_rate"] == 190

    async def test_events(self, cli: CliProcess) -> None:
        """Events lists events soonest first."""
        code, out, _ = await cli.run("events")

        lines = out.strip().splitlines()
        assert code == 0
        assert "Saturday Morning Ride" in lines[0]
        assert "Evening Race" in lines[1]

    async def test_write(self, cli: CliProcess, fake_rouvy: FakeRouvy) -> None:
        """A write command reaches the portal."""
        code, out, _ = await cli.run("set-max-hr", "184")

        assert code == 0
        assert "184 bpm" in out
        assert fake_rouvy.state.posts_to(Endpoint.ZONES)[-1]["value"] == "184"

    async def test_invalid_password(self, cli: CliProcess) -> None:
        """A wrong password exits 1 with a clean message and no traceback."""
        code, out, err = await cli.run("profile", password="wrong-pass-123")

        assert code == 1
        assert out == ""
        assert err.strip() == "error: Invalid Rouvy email or password"
        assert "Traceback" not in err
        assert "wrong-pass-123" not in err

    async def test_usage_error(self, cli: CliProcess) -> None:
        """Bad arguments exit 2 with usage help."""
        code, _, err = await cli.run("set-zones", "power", "90,50")

        assert code == 2
        assert "usage:" in err
