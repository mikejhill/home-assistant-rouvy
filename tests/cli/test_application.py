"""Tests for the CLI application against the fake Rouvy portal."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from rouvy_api import ClientConfig
from rouvy_api.cli.application import EXIT_ERROR, EXIT_OK, Application
from rouvy_api.cli.command_line import CommandLine
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy
from tests.support.rouvy_payloads import CHALLENGE_SLUG, EVENT_ID


class CliRun:
    """Run the application in-process and capture its output."""

    def __init__(self, code: int, stdout: str, stderr: str) -> None:
        self.code = code
        self.stdout = stdout
        self.stderr = stderr

    def json(self) -> object:
        """Parse stdout as JSON."""
        return json.loads(self.stdout)

    @classmethod
    async def invoke(cls, *argv: str) -> CliRun:
        """Run a command and return its exit status and output."""
        stdout, stderr = io.StringIO(), io.StringIO()
        app = Application(stdout=stdout, stderr=stderr)
        code = await app.execute(CommandLine().parse(list(argv)))
        return cls(code, stdout.getvalue(), stderr.getvalue())


@pytest.fixture(autouse=True)
def cli_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client_config: ClientConfig
) -> None:
    """Run in an empty directory with credentials for the fake portal."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ROUVY_EMAIL", VALID_EMAIL)
    monkeypatch.setenv("ROUVY_PASSWORD", VALID_PASSWORD)
    monkeypatch.setenv("ROUVY_BASE_URL", client_config.base_url)


class TestReadCommands:
    """Read commands print text or JSON."""

    async def test_login_check(self) -> None:
        """login-check confirms the account."""
        run = await CliRun.invoke("login-check")

        assert run.code == EXIT_OK
        assert run.stdout == f"Logged in as {VALID_EMAIL} (test-rider)\n"

    @pytest.mark.parametrize(
        ("command", "expected_text"),
        [
            (["profile"], "weight_kg"),
            (["zones"], "power zones (%)   55, 75, 90, 105, 120, 150"),
            (["apps"], "Strava"),
            (["overview"], "career level 5 (1067 XP)"),
            (["activities"], "Faistos | Crete"),
            (["activity-stats", "--year", "2026", "--month", "10"], "3 rides"),
            (["challenges"], f"joined  October Climb  ({CHALLENGE_SLUG})"),
            (["routes"], "Flat Loop"),
            (["events"], "Saturday Morning Ride  [registered]"),
            (["achievements"], "earned"),
            (["trophies"], "total"),
            (["raw", "events.data"], '"routes/_main.events._index"'),
        ],
    )
    async def test_text_output(self, command: list[str], expected_text: str) -> None:
        """Each read command prints human-readable lines."""
        run = await CliRun.invoke(*command)

        assert run.code == EXIT_OK, run.stderr
        assert expected_text in run.stdout

    async def test_profile_units(self) -> None:
        """Profile values show their units."""
        run = await CliRun.invoke("profile")

        assert "85.0 kg" in run.stdout
        assert "190 bpm" in run.stdout

    async def test_favorite_routes_only(self) -> None:
        """Routes --favorites omits non-favorites."""
        run = await CliRun.invoke("routes", "--favorites")

        assert "Flat Loop" not in run.stdout
        assert "Col du Galibier" in run.stdout

    @pytest.mark.parametrize(
        ("command", "check"),
        [
            ("profile", "email"),
            ("events", 0),
            ("challenges", 0),
            ("overview", "career"),
        ],
    )
    async def test_json_output(self, command: str, check: str | int) -> None:
        """--json prints parseable JSON."""
        run = await CliRun.invoke("--json", command)

        data = run.json()
        assert run.code == EXIT_OK
        if isinstance(check, str):
            assert isinstance(data, dict)
            assert check in data
        else:
            assert isinstance(data, list)
            assert data[check]

    async def test_empty_list_message(self, fake_rouvy: FakeRouvy) -> None:
        """Empty lists print a friendly message."""
        fake_rouvy.state.bodies[Endpoint.EVENTS] = fake_rouvy.state.bodies[Endpoint.TROPHIES]

        run = await CliRun.invoke("events")

        assert run.stdout == "No events found.\n"


class TestWriteCommands:
    """Write commands submit forms and confirm."""

    @pytest.mark.parametrize(
        ("command", "path", "expected", "message"),
        [
            (["set-weight", "79.5"], Endpoint.USER_SETTINGS_ACTION, {"weight": "79.5"}, "79.5 kg"),
            (["set-height", "181"], Endpoint.USER_SETTINGS_ACTION, {"height": "181.0"}, "181 cm"),
            (
                ["set-units", "IMPERIAL"],
                Endpoint.USER_SETTINGS_ACTION,
                {"units": "IMPERIAL"},
                "IMPERIAL",
            ),
            (["set-ftp", "250"], Endpoint.ZONES, {"ftpSource": "MANUAL", "value": "250"}, "250 W"),
            (["set-ftp", "--estimated"], Endpoint.ZONES, {"ftpSource": "ESTIMATED"}, "estimate"),
            (["set-max-hr", "186"], Endpoint.ZONES, {"value": "186"}, "186 bpm"),
            (
                ["set-zones", "power", "50,70,85,100,115,140"],
                Endpoint.ZONES,
                {"zones": "[50,70,85,100,115,140]"},
                "power zones",
            ),
            (
                ["set-timezone", "Europe/Prague"],
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-profile", "timezone": "Europe/Prague"},
                "Prague",
            ),
            (
                ["set-privacy", "PRIVATE"],
                Endpoint.USER_SETTINGS_ACTION,
                {"privacy": "PRIVATE"},
                "PRIVATE",
            ),
            (
                ["set-profile", "--first-name", "Ada"],
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-profile", "firstName": "Ada"},
                "updated",
            ),
            (
                ["register-challenge", CHALLENGE_SLUG],
                f"challenges/{CHALLENGE_SLUG}.data",
                {"intent": "register"},
                "Joined",
            ),
            (
                ["register-event", EVENT_ID],
                f"events/{EVENT_ID}.data",
                {"intent": "register"},
                "Registered",
            ),
            (
                ["unregister-event", EVENT_ID],
                f"events/{EVENT_ID}.data",
                {"intent": "unregister"},
                "Unregistered",
            ),
        ],
    )
    async def test_write(
        self,
        fake_rouvy: FakeRouvy,
        command: list[str],
        path: str,
        expected: dict[str, str],
        message: str,
    ) -> None:
        """Each write posts the expected fields and prints a confirmation."""
        run = await CliRun.invoke(*command)

        assert run.code == EXIT_OK, run.stderr
        assert expected.items() <= fake_rouvy.state.posts_to(path)[-1].items()
        assert message in run.stdout

    async def test_write_json(self) -> None:
        """Writes print {"ok": true} with --json."""
        run = await CliRun.invoke("--json", "set-weight", "80")

        data = run.json()
        assert isinstance(data, dict)
        assert data["ok"] is True


class TestErrors:
    """Failures exit with status 1 and a readable message, never a traceback or password."""

    async def test_invalid_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A wrong password reports invalid credentials without echoing it."""
        monkeypatch.setenv("ROUVY_PASSWORD", "hunter2-wrong")

        run = await CliRun.invoke("profile")

        assert run.code == EXIT_ERROR
        assert run.stderr == "error: Invalid Rouvy email or password\n"
        assert "hunter2" not in run.stdout + run.stderr

    async def test_missing_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing environment variables are named in the error."""
        monkeypatch.delenv("ROUVY_PASSWORD")

        run = await CliRun.invoke("profile")

        assert run.code == EXIT_ERROR
        assert "ROUVY_EMAIL and ROUVY_PASSWORD" in run.stderr

    async def test_env_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Credentials load from --env-file without overriding the environment."""
        monkeypatch.delenv("ROUVY_PASSWORD")
        env_file = tmp_path / "creds.env"
        env_file.write_text(f"ROUVY_PASSWORD={VALID_PASSWORD}\n", encoding="utf-8")

        run = await CliRun.invoke("--env-file", str(env_file), "login-check")

        assert run.code == EXIT_OK, run.stderr

    async def test_default_env_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A .env file in the working directory is used automatically."""
        monkeypatch.delenv("ROUVY_PASSWORD")
        (tmp_path / ".env").write_text(f"ROUVY_PASSWORD={VALID_PASSWORD}\n", encoding="utf-8")

        run = await CliRun.invoke("login-check")

        assert run.code == EXIT_OK, run.stderr

    async def test_missing_env_file(self) -> None:
        """A named env file that does not exist is an error."""
        run = await CliRun.invoke("--env-file", "nope.env", "profile")

        assert run.code == EXIT_ERROR
        assert "nope.env" in run.stderr

    async def test_invalid_email(self) -> None:
        """An email override without '@' is rejected before contacting Rouvy."""
        run = await CliRun.invoke("--email", "nobody", "profile")

        assert run.code == EXIT_ERROR
        assert "email" in run.stderr

    async def test_server_error(self, fake_rouvy: FakeRouvy) -> None:
        """A Rouvy server error is reported, not raised."""
        fake_rouvy.state.failures[Endpoint.EVENTS] = 500

        run = await CliRun.invoke("events")

        assert run.code == EXIT_ERROR
        assert "HTTP 500" in run.stderr

    async def test_invalid_raw_route(self) -> None:
        """Raw only accepts relative .data routes."""
        run = await CliRun.invoke("raw", "https://evil.example/x.data")

        assert run.code == EXIT_ERROR
        assert "relative '.data' route" in run.stderr


class TestRun:
    """The synchronous entry point."""

    def test_run_returns_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run() configures logging and returns the command's status."""
        monkeypatch.delenv("ROUVY_EMAIL")
        stderr = io.StringIO()

        code = Application(stdout=io.StringIO(), stderr=stderr).run(["profile"])

        assert code == EXIT_ERROR
        assert "ROUVY_EMAIL" in stderr.getvalue()

    def test_keyboard_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ctrl+C exits with status 130."""

        async def interrupted(_self: Application, _settings: object) -> int:
            raise KeyboardInterrupt

        monkeypatch.setattr(Application, "execute", interrupted)
        stderr = io.StringIO()

        code = Application(stdout=io.StringIO(), stderr=stderr).run(["profile"])

        assert code == 130
        assert stderr.getvalue() == "interrupted\n"

    def test_unencodable_output_is_replaced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cp1252 console gets '?' for emoji instead of a UnicodeEncodeError."""
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1252")
        monkeypatch.setattr("sys.stdout", console)

        Application.tolerate_unencodable_output()
        console.write("Ride 🚴 now")
        console.flush()

        assert raw.getvalue() == b"Ride ? now"

    def test_main_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() exits with run()'s status."""
        monkeypatch.setattr("sys.argv", ["rouvy-api", "--email", "x", "profile"])

        with pytest.raises(SystemExit) as excinfo:
            Application.main()

        assert excinfo.value.code == EXIT_ERROR
