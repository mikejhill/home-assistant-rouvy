"""Async client for the Rouvy riders portal."""

from __future__ import annotations

import asyncio
import dataclasses
import itertools
import logging
import re
import time
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Final, Self

import aiohttp

from rouvy_api.auth import HttpResult, LoginResponseInterpreter, ResponseInspector
from rouvy_api.config import ClientConfig, Credentials, Endpoint
from rouvy_api.exceptions import (
    RouvyApiError,
    RouvyConnectionError,
    RouvyResponseError,
    RouvySessionError,
    RouvyValidationError,
)
from rouvy_api.models import (
    AccountPrivacy,
    AchievementsSummary,
    Challenge,
    ConnectedApp,
    Event,
    FtpSource,
    ProfileOverview,
    Route,
    TrainingZones,
    TrophiesSummary,
    UnitSystem,
    UserProfile,
    WeeklyActivityStats,
    ZoneType,
)
from rouvy_api.parsers import RouvyParser
from rouvy_api.payload import Payload

logger = logging.getLogger(__name__)

type FormValue = str | int | float
type Form = dict[str, FormValue]

_SLUG_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_MIN_YEAR: Final = 2000
_USERNAME_PATTERN: Final = re.compile(r"^[a-zA-Z0-9_.-]{4,25}$")


@dataclass(frozen=True, slots=True)
class ProfileUpdate:
    """Profile identity fields to change; None leaves a field unchanged."""

    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    country: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    timezone: str | None = None
    language: str | None = None

    @property
    def is_empty(self) -> bool:
        """Return True when no field would change."""
        return all(getattr(self, item.name) is None for item in dataclasses.fields(self))


class RouvyClient:
    """Authenticated access to Rouvy rider data.

    The aiohttp session must be dedicated to this client: logging in clears the
    session's cookies for the Rouvy host.
    """

    def __init__(
        self,
        credentials: Credentials,
        session: aiohttp.ClientSession,
        *,
        config: ClientConfig | None = None,
    ) -> None:
        self._credentials = credentials
        self._session = session
        self._config = config or ClientConfig()
        self._parser = RouvyParser()
        self._inspector = ResponseInspector()
        self._login_interpreter = LoginResponseInterpreter(self._inspector)
        self._auth_lock = asyncio.Lock()
        self._session_generation = 0
        self._authenticated = False

    @classmethod
    @asynccontextmanager
    async def open(
        cls, credentials: Credentials, *, config: ClientConfig | None = None
    ) -> AsyncGenerator[Self]:
        """Yield a client that owns (and finally closes) its own aiohttp session."""
        resolved = config or ClientConfig()
        async with aiohttp.ClientSession(cookie_jar=resolved.cookie_jar()) as session:
            yield cls(credentials, session, config=resolved)

    @property
    def email(self) -> str:
        """Return the account email."""
        return self._credentials.email

    @property
    def is_authenticated(self) -> bool:
        """Return True once a session has been established."""
        return self._authenticated

    # Authentication

    async def login(self) -> None:
        """Log in and verify that Rouvy issued a working session.

        Raises:
            RouvyAuthenticationError: If the credentials are rejected or no session results.
            RouvyConnectionError: If Rouvy cannot be reached.
        """
        async with self._auth_lock:
            await self._login_locked()

    async def validate_credentials(self) -> UserProfile:
        """Log in and return the profile, proving the credentials work end to end."""
        await self.login()
        return await self.get_user_profile()

    # Reads

    async def get_user_profile(self) -> UserProfile:
        """Return the rider profile."""
        return self._parser.user_profile(await self._get(Endpoint.USER_SETTINGS))

    async def get_training_zones(self) -> TrainingZones:
        """Return FTP, max heart rate, and zone boundaries."""
        return self._parser.training_zones(await self._get(Endpoint.ZONES))

    async def get_connected_apps(self) -> list[ConnectedApp]:
        """Return linked third-party services."""
        return self._parser.connected_apps(await self._get(Endpoint.CONNECTED_APPS))

    async def get_profile_overview(self) -> ProfileOverview:
        """Return recent activities, period totals, career progress, and friends."""
        return self._parser.profile_overview(await self._get(Endpoint.PROFILE_OVERVIEW))

    async def get_weekly_activity_stats(self, year: int, month: int) -> list[WeeklyActivityStats]:
        """Return weekly totals for the weeks of a calendar month."""
        if not 1 <= month <= 12 or year < _MIN_YEAR:  # noqa: PLR2004
            msg = f"Invalid month {year}-{month:02d}"
            raise RouvyValidationError(msg)
        payload = await self._post(Endpoint.ACTIVITY_STATS, {"year": year, "month": month})
        return self._parser.weekly_activity_stats(payload)

    async def get_challenges(self) -> list[Challenge]:
        """Return challenges currently offered to the rider."""
        return self._parser.challenges(await self._get(Endpoint.CHALLENGES))

    async def get_routes(self) -> list[Route]:
        """Return routes listed on the routes page."""
        return self._parser.routes(await self._get(Endpoint.ROUTES))

    async def get_favorite_routes(self) -> list[Route]:
        """Return the routes in the rider's favourites collection."""
        return self._parser.favorite_routes(await self._get(Endpoint.FAVORITE_ROUTES))

    async def get_events(self) -> list[Event]:
        """Return upcoming events ordered by start time."""
        return self._parser.events(await self._get(Endpoint.EVENTS))

    async def get_achievements(self) -> AchievementsSummary:
        """Return achievement progress."""
        return self._parser.achievements(await self._get(Endpoint.ACHIEVEMENTS))

    async def get_trophies(self) -> TrophiesSummary:
        """Return trophy counts."""
        return self._parser.trophies(await self._get(Endpoint.TROPHIES))

    async def get_payload(self, path: str) -> Payload:
        """Return the decoded payload of any riders-portal ``.data`` route."""
        if not path.endswith(".data") or "://" in path or ".." in path:
            msg = f"Path must be a relative '.data' route, got {path!r}"
            raise RouvyValidationError(msg)
        return await self._get(path)

    # Writes

    async def update_body_metrics(
        self,
        *,
        weight_kg: float | None = None,
        height_cm: float | None = None,
        units: UnitSystem | None = None,
    ) -> None:
        """Change weight, height, and/or the unit system."""
        if weight_kg is None and height_cm is None and units is None:
            msg = "Provide at least one of weight_kg, height_cm, or units"
            raise RouvyValidationError(msg)
        self._require_positive(weight_kg=weight_kg, height_cm=height_cm)
        current = await self.get_user_profile()
        weight = self._first(weight_kg, current.weight_kg)
        height = self._first(height_cm, current.height_cm)
        if weight is None or height is None:
            msg = "Rouvy requires both weight and height; supply the one missing from the profile"
            raise RouvyValidationError(msg)
        form: Form = {
            "intent": "update-units",
            "weight": weight,
            "height": height,
            "units": str(units or current.units),
        }
        await self._post(Endpoint.USER_SETTINGS_ACTION, form)

    async def update_profile(self, update: ProfileUpdate) -> None:
        """Change profile identity fields, keeping every other field as it is."""
        if update.is_empty:
            msg = "ProfileUpdate does not change any field"
            raise RouvyValidationError(msg)
        self._validate_profile_update(update)
        current = await self.get_user_profile()
        username = update.username or current.username
        gender = update.gender or current.gender
        country = update.country or current.country
        if username is None or gender is None or country is None:
            msg = "Rouvy requires a username, gender, and country; supply the missing values"
            raise RouvyValidationError(msg)
        form: Form = {
            "intent": "update-profile",
            "currentUsername": current.username or "",
            "username": username,
            "firstName": self._first(update.first_name, current.first_name or ""),
            "lastName": self._first(update.last_name, current.last_name or ""),
            "gender": gender,
            "countryIsoCode": country,
            "timezone": update.timezone or current.timezone or "UTC",
            "language": update.language or current.language or "en",
        }
        birth_date = update.birth_date or current.birth_date
        if birth_date is not None:
            form["dateOfBirth"] = birth_date.isoformat()
        await self._post(Endpoint.USER_SETTINGS_ACTION, form)

    async def update_account_privacy(self, privacy: AccountPrivacy) -> None:
        """Make the account public or private."""
        await self._post(
            Endpoint.USER_SETTINGS_ACTION, {"intent": "update-social", "privacy": str(privacy)}
        )

    async def update_timezone(self, timezone: str) -> None:
        """Set the rider's IANA timezone (part of Rouvy's profile form)."""
        await self.update_profile(ProfileUpdate(timezone=timezone))

    async def update_ftp(self, source: FtpSource, watts: int | None = None) -> None:
        """Switch FTP between estimated and a manual value."""
        if source is FtpSource.MANUAL and (watts is None or watts <= 0):
            msg = "A positive watts value is required for a manual FTP"
            raise RouvyValidationError(msg)
        zones = await self.get_training_zones()
        form: Form = {
            "type": str(ZoneType.POWER),
            "ftpSource": str(source),
            "oldValue": zones.ftp_watts or 0,
            "zones": self._zone_list(zones.zones_for(ZoneType.POWER)),
        }
        if source is FtpSource.MANUAL and watts is not None:
            form["value"] = watts
        await self._post(Endpoint.ZONES, form)

    async def update_zones(self, zone_type: ZoneType, boundaries: Iterable[int]) -> None:
        """Replace the zone boundaries (percent of FTP or max heart rate)."""
        values = self._validate_zones(boundaries)
        zones = await self.get_training_zones()
        form: Form = {"type": str(zone_type), "zones": self._zone_list(values)}
        if zone_type is ZoneType.HEART_RATE:
            form["oldValue"] = form["value"] = zones.max_heart_rate or 0
        else:
            profile = await self.get_user_profile()
            source = profile.ftp_source or FtpSource.ESTIMATED
            form["ftpSource"] = source
            form["oldValue"] = zones.ftp_watts or 0
            if source == FtpSource.MANUAL:
                form["value"] = zones.ftp_watts or 0
        await self._post(Endpoint.ZONES, form)

    async def update_max_heart_rate(self, bpm: int) -> None:
        """Set the maximum heart rate, keeping the heart-rate zone boundaries."""
        if not 60 <= bpm <= 250:  # noqa: PLR2004
            msg = f"Max heart rate must be between 60 and 250 bpm, got {bpm}"
            raise RouvyValidationError(msg)
        zones = await self.get_training_zones()
        form: Form = {
            "type": str(ZoneType.HEART_RATE),
            "oldValue": zones.max_heart_rate or 0,
            "value": bpm,
            "zones": self._zone_list(zones.zones_for(ZoneType.HEART_RATE)),
        }
        await self._post(Endpoint.ZONES, form)

    async def register_challenge(self, slug: str) -> None:
        """Join a challenge."""
        await self._post(f"challenges/{self._slug(slug)}.data", {"intent": "register"})

    async def register_event(self, event_id: str) -> None:
        """Join an event."""
        event = self._slug(event_id)
        await self._post(f"events/{event}.data", {"intent": "register", "eventId": event})

    async def unregister_event(self, event_id: str) -> None:
        """Leave an event."""
        event = self._slug(event_id)
        await self._post(f"events/{event}.data", {"intent": "unregister", "eventId": event})

    # Transport

    async def _get(self, path: str) -> Payload:
        """GET a data route with session handling."""
        return await self._request("GET", path, None)

    async def _post(self, path: str, form: Form) -> Payload:
        """POST a form to an action route with session handling."""
        return await self._request("POST", path, form)

    async def _request(self, method: str, path: str, form: Form | None) -> Payload:
        """Send a request, re-authenticating once if the session has expired."""
        for attempt in range(2):
            generation = await self._ensure_session()
            result = await self._send(method, path, form)
            if self._inspector.is_unauthorized(result):
                payload = None
            else:
                payload = self._inspector.parse(result, context=f"{method} {path}")
                if not self._inspector.is_sign_in_redirect(payload):
                    self._check_redirect(payload, method=method, path=path)
                    self._raise_for_action_error(payload, path=path)
                    return payload
            logger.info("Rouvy session expired during %s %s; logging in again", method, path)
            if attempt == 0:
                await self._invalidate(generation)
        msg = f"Rouvy did not accept the session for {method} {path} after logging in again"
        raise RouvySessionError(msg)

    async def _ensure_session(self) -> int:
        """Log in when needed and return the session generation in use."""
        async with self._auth_lock:
            if not self._authenticated:
                await self._login_locked()
        return self._session_generation

    async def _invalidate(self, generation: int) -> None:
        """Mark the session expired unless another request already renewed it."""
        async with self._auth_lock:
            if generation == self._session_generation:
                self._authenticated = False

    async def _login_locked(self) -> None:
        """Perform the login handshake; caller holds the auth lock."""
        logger.debug("Logging in to Rouvy as %s", self._credentials.email)
        self._authenticated = False
        self._session.cookie_jar.clear_domain(self._config.host)
        form: Form = {"email": self._credentials.email, "password": self._credentials.password}
        self._login_interpreter.verify(await self._send("POST", Endpoint.LOGIN, form))

        # Prove the session works: Rouvy answers unauthenticated reads with a sign-in redirect
        check = await self._send("GET", Endpoint.USER_SETTINGS, None)
        if self._inspector.is_unauthorized(check) or self._inspector.is_sign_in_redirect(
            self._inspector.parse(check, context="Session check")
        ):
            msg = (
                "Rouvy accepted the credentials but did not start a session. "
                "Rouvy's login flow may have changed; please report this."
            )
            raise RouvySessionError(msg)
        self._session_generation += 1
        self._authenticated = True
        logger.info("Logged in to Rouvy")

    async def _send(self, method: str, path: str, form: Form | None) -> HttpResult:
        """Send one HTTP request and return its status and body."""
        url = self._config.url(path)
        headers = {"User-Agent": self._config.user_agent, "Accept": "*/*"}
        data = {key: str(value) for key, value in form.items()} if form is not None else None
        started = time.perf_counter()
        try:
            async with self._session.request(
                method,
                url,
                data=data,
                headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=self._config.timeout_s),
            ) as response:
                text = await response.text()
                result = HttpResult(response.status, response.content_type, text)
        except TimeoutError as err:
            msg = f"Timed out after {self._config.timeout_s:g}s calling Rouvy ({method} {path})"
            raise RouvyConnectionError(msg) from err
        except aiohttp.ClientError as err:
            msg = f"Could not reach Rouvy ({method} {path}): {err}"
            raise RouvyConnectionError(msg) from err
        logger.debug(
            "%s %s -> %s in %.0f ms",
            method,
            path,
            result.status,
            (time.perf_counter() - started) * 1000,
        )
        return result

    @staticmethod
    def _check_redirect(payload: Payload, *, method: str, path: str) -> None:
        """Reject unexpected redirects on reads; actions commonly redirect on success."""
        location = payload.redirect_location
        if location is not None and method == "GET":
            msg = f"GET {path} unexpectedly redirected to {location}"
            raise RouvyResponseError(msg)

    @staticmethod
    def _raise_for_action_error(payload: Payload, *, path: str) -> None:
        """Raise when an action reports a form error."""
        data = payload.action_data
        if data is None or data.text("status") != "error":
            return
        detail = data.raw.get("error")
        msg = f"Rouvy rejected the update to {path}: {detail!r}"
        raise RouvyApiError(msg)

    # Validation helpers

    @staticmethod
    def _first[T](preferred: T | None, fallback: T) -> T:
        """Return the preferred value unless it is None."""
        return fallback if preferred is None else preferred

    @staticmethod
    def _require_positive(**values: float | None) -> None:
        """Reject zero or negative measurements."""
        for name, value in values.items():
            if value is not None and value <= 0:
                msg = f"{name} must be positive, got {value}"
                raise RouvyValidationError(msg)

    @staticmethod
    def _validate_profile_update(update: ProfileUpdate) -> None:
        """Apply the same rules as Rouvy's profile form."""
        if update.username is not None and not _USERNAME_PATTERN.fullmatch(update.username):
            msg = "Usernames need 4-25 letters, digits, '.', '_' or '-'"
            raise RouvyValidationError(msg)
        timezone = update.timezone
        if timezone is not None and "/" not in timezone and timezone != "UTC":
            msg = f"Expected an IANA timezone such as Europe/Prague, got {timezone!r}"
            raise RouvyValidationError(msg)

    @staticmethod
    def _validate_zones(boundaries: Iterable[int]) -> tuple[int, ...]:
        """Require a non-empty, strictly increasing list of positive percentages."""
        values = tuple(boundaries)
        if not values or any(v <= 0 for v in values):
            msg = "Zone boundaries must be a non-empty list of positive percentages"
            raise RouvyValidationError(msg)
        if any(b <= a for a, b in itertools.pairwise(values)):
            msg = f"Zone boundaries must be strictly increasing, got {list(values)}"
            raise RouvyValidationError(msg)
        return values

    @staticmethod
    def _zone_list(values: Iterable[int]) -> str:
        """Encode zone boundaries the way Rouvy's form expects (``[55,75,...]``)."""
        return "[" + ",".join(str(v) for v in values) + "]"

    @staticmethod
    def _slug(value: str) -> str:
        """Validate an identifier used as a URL path segment."""
        if not _SLUG_PATTERN.fullmatch(value):
            msg = f"Invalid identifier {value!r}; expected letters, digits, '-' or '_'"
            raise RouvyValidationError(msg)
        return value
