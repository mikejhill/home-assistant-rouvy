"""Tests for RouvyClient against the fake Rouvy portal."""

from __future__ import annotations

import asyncio
import socket
from datetime import date

import aiohttp
import pytest

from rouvy_api import (
    AccountPrivacy,
    ClientConfig,
    Credentials,
    Endpoint,
    FtpSource,
    ProfileUpdate,
    RouvyAccountDisabledError,
    RouvyApiError,
    RouvyBlockedError,
    RouvyClient,
    RouvyConnectionError,
    RouvyInvalidCredentialsError,
    RouvyResponseError,
    RouvySessionError,
    RouvyValidationError,
    UnitSystem,
    ZoneType,
)
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD, FakeRouvy
from tests.support.rouvy_payloads import CHALLENGE_SLUG, EVENT_ID, RouvyPayloads


class ClientFactory:
    """Create clients with custom settings against the fake portal."""

    @staticmethod
    def create(
        session: aiohttp.ClientSession,
        config: ClientConfig,
        *,
        password: str = VALID_PASSWORD,
    ) -> RouvyClient:
        """Return a client."""
        return RouvyClient(Credentials(VALID_EMAIL, password), session, config=config)


@pytest.fixture
async def session(client_config: ClientConfig) -> aiohttp.ClientSession:
    """A session with a cookie jar that accepts the fake portal's cookies."""
    return aiohttp.ClientSession(cookie_jar=client_config.cookie_jar())


class TestLogin:
    """Authentication outcomes."""

    async def test_login_identifies_the_project(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Login posts the credentials with the project user agent and verifies the session."""
        await rouvy_client.login()

        login, check = fake_rouvy.state.requests[:2]
        assert login.path == Endpoint.LOGIN
        assert login.form == {"email": VALID_EMAIL, "password": VALID_PASSWORD}
        assert login.user_agent.startswith("home-assistant-rouvy/")
        assert check.path == Endpoint.USER_SETTINGS
        assert rouvy_client.is_authenticated
        assert rouvy_client.email == VALID_EMAIL

    async def test_invalid_credentials(
        self, session: aiohttp.ClientSession, client_config: ClientConfig
    ) -> None:
        """A wrong password raises RouvyInvalidCredentialsError."""
        async with session:
            client = ClientFactory.create(session, client_config, password="nope")
            with pytest.raises(RouvyInvalidCredentialsError):
                await client.login()
            assert not client.is_authenticated

    async def test_disabled_account(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """A disabled account raises RouvyAccountDisabledError."""
        fake_rouvy.state.disabled_accounts.add(VALID_EMAIL)

        with pytest.raises(RouvyAccountDisabledError):
            await rouvy_client.login()

    async def test_no_session_cookie(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Accepted credentials without a session raise RouvySessionError."""
        fake_rouvy.state.issue_session_cookie = False

        with pytest.raises(RouvySessionError, match="did not start a session"):
            await rouvy_client.login()

    async def test_blocked_user_agent(
        self, session: aiohttp.ClientSession, client_config: ClientConfig
    ) -> None:
        """A generic library user agent is rejected by the firewall (why v1 broke)."""
        config = ClientConfig(base_url=client_config.base_url, user_agent="python-requests/2.32")
        async with session:
            with pytest.raises(RouvyBlockedError):
                await ClientFactory.create(session, config).login()

    async def test_validate_credentials_returns_profile(self, rouvy_client: RouvyClient) -> None:
        """validate_credentials logs in and returns the profile."""
        profile = await rouvy_client.validate_credentials()

        assert profile.email == "rider@example.com"


class TestSessionRenewal:
    """Transparent re-authentication."""

    async def test_expired_session_relogs_once(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """An expired session triggers exactly one new login and the read succeeds."""
        await rouvy_client.get_user_profile()
        fake_rouvy.state.expire_sessions()

        zones = await rouvy_client.get_training_zones()

        assert zones.max_heart_rate == 190
        assert fake_rouvy.state.login_count == 2

    async def test_concurrent_reads_share_one_login(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Concurrent requests after expiry log in only once."""
        await rouvy_client.login()
        fake_rouvy.state.expire_sessions()

        await asyncio.gather(*(rouvy_client.get_user_profile() for _ in range(5)))

        assert fake_rouvy.state.login_count == 2

    async def test_unauthorized_status_relogs(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """HTTP 401 also triggers a new login, and a persistent 401 is a session error."""
        await rouvy_client.login()
        fake_rouvy.state.failures[Endpoint.EVENTS] = 401

        with pytest.raises(RouvySessionError, match="after logging in again"):
            await rouvy_client.get_events()

        assert fake_rouvy.state.login_count == 2

    async def test_persistent_redirect(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """If reads keep redirecting to sign-in after a new login, give up with a session error."""
        await rouvy_client.login()
        fake_rouvy.state.bodies[Endpoint.EVENTS] = RouvyPayloads().sign_in_redirect("events.data")

        with pytest.raises(RouvySessionError):
            await rouvy_client.get_events()


class TestTransportErrors:
    """Network and server failures."""

    async def test_server_error(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """HTTP 500 raises RouvyApiError with the status."""
        fake_rouvy.state.failures[Endpoint.CHALLENGES] = 500

        with pytest.raises(RouvyApiError) as excinfo:
            await rouvy_client.get_challenges()

        assert excinfo.value.status == 500

    async def test_timeout(
        self, session: aiohttp.ClientSession, client_config: ClientConfig, fake_rouvy: FakeRouvy
    ) -> None:
        """A slow portal raises RouvyConnectionError."""
        fake_rouvy.state.latency_s = 1.0
        config = ClientConfig(base_url=client_config.base_url, timeout_s=0.1)
        async with session:
            with pytest.raises(RouvyConnectionError, match="Timed out"):
                await ClientFactory.create(session, config).login()

    async def test_connection_refused(
        self, session: aiohttp.ClientSession, socket_enabled: None
    ) -> None:
        """An unreachable portal raises RouvyConnectionError."""
        del socket_enabled
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        config = ClientConfig(base_url=f"http://127.0.0.1:{port}")
        async with session:
            with pytest.raises(RouvyConnectionError, match="Could not reach"):
                await ClientFactory.create(session, config).login()

    async def test_unexpected_read_redirect(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """A read that redirects somewhere other than sign-in is a response error."""
        fake_rouvy.state.bodies[Endpoint.TROPHIES] = RouvyPayloads().redirect("/onboarding")

        with pytest.raises(RouvyResponseError, match="/onboarding"):
            await rouvy_client.get_trophies()

    async def test_action_form_error(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """An action that returns a form error raises RouvyApiError."""
        fake_rouvy.state.bodies["form-error.data"] = RouvyPayloads.encode(
            {"data": {"status": "error", "error": {"timezone": ["Invalid"]}}}
        )
        await rouvy_client.login()

        # The fake answers POSTs with success, so read the error body via GET semantics
        with pytest.raises(RouvyApiError, match="rejected the update"):
            await rouvy_client.get_payload("form-error.data")


class TestReads:
    """Every read method returns parsed models."""

    async def test_all_reads(self, rouvy_client: RouvyClient) -> None:
        """Reads parse the fake portal's responses."""
        assert (await rouvy_client.get_user_profile()).max_heart_rate == 190
        assert (await rouvy_client.get_training_zones()).power_zones[0] == 55
        assert len(await rouvy_client.get_connected_apps()) == 17
        assert len((await rouvy_client.get_profile_overview()).recent_activities) == 10
        assert len(await rouvy_client.get_weekly_activity_stats(2026, 10)) == 2
        assert len(await rouvy_client.get_challenges()) == 3
        assert len(await rouvy_client.get_routes()) == 3
        assert len(await rouvy_client.get_favorite_routes()) == 2
        assert (await rouvy_client.get_events())[0].event_id == EVENT_ID
        assert (await rouvy_client.get_achievements()).earned == 2
        assert (await rouvy_client.get_trophies()).total == 4
        assert (await rouvy_client.get_payload("events.data")).find("featuredEvents") is not None

    @pytest.mark.parametrize(("year", "month"), [(2026, 0), (2026, 13), (1999, 5)])
    async def test_invalid_month(self, rouvy_client: RouvyClient, year: int, month: int) -> None:
        """Invalid months are rejected before any request."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.get_weekly_activity_stats(year, month)

    @pytest.mark.parametrize("path", ["https://evil.example/x.data", "../x.data", "events"])
    async def test_invalid_raw_path(self, rouvy_client: RouvyClient, path: str) -> None:
        """Raw reads only accept relative .data routes."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.get_payload(path)


class TestWrites:
    """Every write submits the form Rouvy expects."""

    async def test_body_metrics_keep_current_values(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Changing weight keeps the current height and units."""
        await rouvy_client.update_body_metrics(weight_kg=80.5)

        assert fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-1] == {
            "intent": "update-units",
            "weight": "80.5",
            "height": "178.0",
            "units": "METRIC",
        }

    async def test_units(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """Units can change alone."""
        await rouvy_client.update_body_metrics(units=UnitSystem.IMPERIAL)

        assert fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-1]["units"] == "IMPERIAL"

    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"weight_kg": 0.0}, {"height_cm": -5.0}],
        ids=["nothing", "zero-weight", "negative-height"],
    )
    async def test_body_metrics_validation(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, kwargs: dict[str, float]
    ) -> None:
        """Invalid body metrics fail before any request."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_body_metrics(
                weight_kg=kwargs.get("weight_kg"), height_cm=kwargs.get("height_cm")
            )

        assert fake_rouvy.state.requests == []

    async def test_body_metrics_need_existing_height(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, payloads: RouvyPayloads
    ) -> None:
        """If the profile lacks a height, a weight-only change asks for it."""
        fake_rouvy.state.bodies[Endpoint.USER_SETTINGS] = payloads.encode(
            {"userProfile": {"weight": 80}}
        )

        with pytest.raises(RouvyValidationError, match="weight and height"):
            await rouvy_client.update_body_metrics(weight_kg=81)

    async def test_profile_update(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """Profile updates resend the current identity with the changes applied."""
        await rouvy_client.update_profile(ProfileUpdate(first_name="Ada", language="cs"))

        form = fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-1]
        assert form == {
            "intent": "update-profile",
            "currentUsername": "test-rider",
            "username": "test-rider",
            "firstName": "Ada",
            "lastName": "",
            "gender": "MALE",
            "countryIsoCode": "US",
            "timezone": "America/New_York",
            "language": "cs",
            "dateOfBirth": "1990-01-01",
        }

    async def test_profile_update_requires_identity(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, payloads: RouvyPayloads
    ) -> None:
        """Missing gender or country must be supplied, never invented; birth date is optional."""
        fake_rouvy.state.bodies[Endpoint.USER_SETTINGS] = payloads.encode(
            {"userProfile": {"userName": "rider1"}}
        )

        with pytest.raises(RouvyValidationError, match="username, gender, and country"):
            await rouvy_client.update_profile(ProfileUpdate(first_name="Ada"))

        await rouvy_client.update_profile(
            ProfileUpdate(
                first_name="Ada", gender="MALE", country="US", birth_date=date(1990, 1, 1)
            )
        )
        await rouvy_client.update_profile(
            ProfileUpdate(first_name="Ada", gender="MALE", country="US")
        )
        form = fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-1]
        assert "dateOfBirth" not in form
        assert (form["timezone"], form["language"]) == ("UTC", "en")

    @pytest.mark.parametrize(
        "update",
        [
            ProfileUpdate(username="abc"),
            ProfileUpdate(username="has space"),
            ProfileUpdate(timezone="EST"),
        ],
        ids=["short-username", "bad-username", "bad-timezone"],
    )
    async def test_profile_validation(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, update: ProfileUpdate
    ) -> None:
        """Profile values Rouvy's form would reject fail before any request."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_profile(update)

        assert fake_rouvy.state.requests == []

    async def test_profile_update_empty(self, rouvy_client: RouvyClient) -> None:
        """An empty update is rejected."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_profile(ProfileUpdate())

    async def test_privacy_and_timezone(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Privacy has its own intent; timezone goes through the profile form."""
        await rouvy_client.update_account_privacy(AccountPrivacy.PRIVATE)
        await rouvy_client.update_timezone("Europe/Prague")

        privacy, timezone = fake_rouvy.state.posts_to(Endpoint.USER_SETTINGS_ACTION)[-2:]
        assert privacy == {"intent": "update-social", "privacy": "PRIVATE"}
        assert timezone["intent"] == "update-profile"
        assert timezone["timezone"] == "Europe/Prague"

    async def test_invalid_timezone(self, rouvy_client: RouvyClient) -> None:
        """Timezones must be IANA names."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_timezone("EST")

    async def test_manual_and_estimated_ftp(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Manual FTP sends a value; estimated FTP does not."""
        await rouvy_client.update_ftp(FtpSource.MANUAL, 250)
        await rouvy_client.update_ftp(FtpSource.ESTIMATED)

        manual, estimated = fake_rouvy.state.posts_to(Endpoint.ZONES)[-2:]
        assert manual == {
            "type": "power",
            "ftpSource": "MANUAL",
            "oldValue": "0",
            "zones": "[55,75,90,105,120,150]",
            "value": "250",
        }
        assert "value" not in estimated

    @pytest.mark.parametrize("watts", [None, 0])
    async def test_manual_ftp_requires_watts(
        self, rouvy_client: RouvyClient, watts: int | None
    ) -> None:
        """Manual FTP needs a positive value."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_ftp(FtpSource.MANUAL, watts)

    async def test_zones(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """Power zones carry the FTP source; heart-rate zones carry max HR."""
        await rouvy_client.update_zones(ZoneType.POWER, [50, 70, 85])
        await rouvy_client.update_zones(ZoneType.HEART_RATE, [60, 70, 80])

        power, heart = fake_rouvy.state.posts_to(Endpoint.ZONES)[-2:]
        assert power == {
            "type": "power",
            "zones": "[50,70,85]",
            "ftpSource": "ESTIMATED",
            "oldValue": "0",
        }
        assert heart == {
            "type": "heartRate",
            "zones": "[60,70,80]",
            "oldValue": "190",
            "value": "190",
        }

    async def test_manual_ftp_zones_keep_value(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, payloads: RouvyPayloads
    ) -> None:
        """With a manual FTP, power zone updates resend the FTP value."""
        fake_rouvy.state.bodies[Endpoint.USER_SETTINGS] = payloads.encode(
            {"userProfile": {"ftpSource": "MANUAL", "ftp": 240}}
        )
        fake_rouvy.state.bodies[Endpoint.ZONES] = payloads.encode(
            {"config": {"power": {"value": 240, "zones": [{"value": 55}]}}}
        )

        await rouvy_client.update_zones(ZoneType.POWER, [56])

        assert fake_rouvy.state.posts_to(Endpoint.ZONES)[-1]["value"] == "240"

    @pytest.mark.parametrize("zones", [[], [0, 50], [60, 50], [50, 50]])
    async def test_zone_validation(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy, zones: list[int]
    ) -> None:
        """Bad boundaries fail before any request."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_zones(ZoneType.POWER, zones)

        assert fake_rouvy.state.requests == []

    async def test_max_heart_rate(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """Max heart rate keeps the current heart-rate zones."""
        await rouvy_client.update_max_heart_rate(185)

        assert fake_rouvy.state.posts_to(Endpoint.ZONES)[-1] == {
            "type": "heartRate",
            "oldValue": "190",
            "value": "185",
            "zones": "[60,65,75,82,89,94]",
        }

    @pytest.mark.parametrize("bpm", [59, 251])
    async def test_max_heart_rate_bounds(self, rouvy_client: RouvyClient, bpm: int) -> None:
        """Implausible heart rates are rejected."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.update_max_heart_rate(bpm)

    async def test_registrations(self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy) -> None:
        """Challenge and event registrations post to their pages."""
        await rouvy_client.register_challenge(CHALLENGE_SLUG)
        await rouvy_client.register_event(EVENT_ID)
        await rouvy_client.unregister_event(EVENT_ID)

        assert fake_rouvy.state.posts_to(f"challenges/{CHALLENGE_SLUG}.data") == [
            {"intent": "register"}
        ]
        assert [f["intent"] for f in fake_rouvy.state.posts_to(f"events/{EVENT_ID}.data")] == [
            "register",
            "unregister",
        ]

    @pytest.mark.parametrize("slug", ["../admin", "", "a/b", "x" * 200])
    async def test_slug_validation(self, rouvy_client: RouvyClient, slug: str) -> None:
        """Identifiers that could escape the URL path are rejected."""
        with pytest.raises(RouvyValidationError):
            await rouvy_client.register_challenge(slug)


class TestConfiguration:
    """Credentials and configuration value objects."""

    def test_password_hidden_in_repr(self) -> None:
        """repr(Credentials) never shows the password."""
        assert VALID_PASSWORD not in repr(Credentials(VALID_EMAIL, VALID_PASSWORD))

    @pytest.mark.parametrize(("email", "password"), [("no-at-sign", "x"), ("a@b.c", "")])
    def test_invalid_credentials(self, email: str, password: str) -> None:
        """Unusable credentials are rejected."""
        with pytest.raises(ValueError, match="Credentials"):
            Credentials(email, password)

    @pytest.mark.parametrize(
        ("base_url", "timeout"),
        [("ftp://x", 1.0), ("relative/path", 1.0), ("https://x", 0.0)],
    )
    def test_invalid_config(self, base_url: str, timeout: float) -> None:
        """Bad URLs and timeouts are rejected."""
        with pytest.raises(ValueError, match="must be"):
            ClientConfig(base_url=base_url, timeout_s=timeout)

    async def test_cookie_jar_for_ip_host(self) -> None:
        """IP hosts get a jar that accepts their cookies; names get a normal jar."""
        assert ClientConfig(base_url="http://127.0.0.1:8123").cookie_jar()._unsafe
        assert not ClientConfig().cookie_jar()._unsafe

    def test_url(self) -> None:
        """url() joins paths without doubling slashes."""
        assert ClientConfig(base_url="https://x/").url("/a.data") == "https://x/a.data"

    async def test_open_owns_session(self, client_config: ClientConfig) -> None:
        """RouvyClient.open yields a working client and closes its session."""
        async with RouvyClient.open(
            Credentials(VALID_EMAIL, VALID_PASSWORD), config=client_config
        ) as client:
            profile = await client.get_user_profile()

        assert profile.max_heart_rate == 190
