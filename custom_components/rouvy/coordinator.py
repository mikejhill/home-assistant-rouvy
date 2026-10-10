"""Data update coordinator that polls Rouvy and keeps the last good data per section."""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.rouvy.api import RouvyConnection
from custom_components.rouvy.const import DOMAIN, LOGGER, MAX_CONCURRENT_REQUESTS, UPDATE_INTERVAL
from custom_components.rouvy.rouvy_api import (
    AchievementsSummary,
    Challenge,
    ConnectedApp,
    Event,
    ProfileOverview,
    Route,
    RouvyAccountDisabledError,
    RouvyClient,
    RouvyError,
    RouvyInvalidCredentialsError,
    TrainingZones,
    TrophiesSummary,
    UserProfile,
    WeeklyActivityStats,
)


@dataclass(frozen=True, slots=True)
class RouvySnapshot:
    """Everything fetched in one refresh; None means the section is unavailable."""

    profile: UserProfile
    fetched_at: datetime
    zones: TrainingZones | None = None
    connected_apps: tuple[ConnectedApp, ...] | None = None
    overview: ProfileOverview | None = None
    weekly_stats: tuple[WeeklyActivityStats, ...] | None = None
    challenges: tuple[Challenge, ...] | None = None
    favorite_routes: tuple[Route, ...] | None = None
    events: tuple[Event, ...] | None = None
    achievements: AchievementsSummary | None = None
    trophies: TrophiesSummary | None = None

    def current_week(self, today: date) -> WeeklyActivityStats | None:
        """Return the weekly stats that contain ``today``."""
        if self.weekly_stats is None:
            return None
        return next((week for week in self.weekly_stats if week.contains(today)), None)

    def upcoming_events(self, now: datetime) -> tuple[Event, ...] | None:
        """Return joined events that have not started yet, soonest first."""
        if self.events is None:
            return None
        return tuple(
            e for e in self.events if e.registered and (e.starts_at is None or e.starts_at >= now)
        )


@dataclass(frozen=True, slots=True)
class RouvyRuntimeData:
    """Objects owned by a loaded config entry."""

    coordinator: RouvyDataUpdateCoordinator
    connection: RouvyConnection


type RouvyConfigEntry = ConfigEntry[RouvyRuntimeData]
type SectionValue = (
    TrainingZones
    | ProfileOverview
    | AchievementsSummary
    | TrophiesSummary
    | tuple[ConnectedApp, ...]
    | tuple[WeeklyActivityStats, ...]
    | tuple[Challenge, ...]
    | tuple[Route, ...]
    | tuple[Event, ...]
)


class RouvyDataUpdateCoordinator(DataUpdateCoordinator[RouvySnapshot]):
    """Fetch the profile (required) and every optional section concurrently."""

    config_entry: RouvyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RouvyConfigEntry, client: RouvyClient) -> None:
        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self._client = client
        self._limit = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._last_sections: dict[str, SectionValue] = {}

    @property
    def client(self) -> RouvyClient:
        """Return the API client."""
        return self._client

    @override
    async def _async_update_data(self) -> RouvySnapshot:
        """Fetch a new snapshot."""
        profile = await self._fetch_profile()
        now = dt_util.now()
        loaders: dict[str, Callable[[], Awaitable[SectionValue]]] = {
            "zones": self._client.get_training_zones,
            "connected_apps": self._tupled(self._client.get_connected_apps),
            "overview": self._client.get_profile_overview,
            "weekly_stats": self._tupled(
                lambda: self._client.get_weekly_activity_stats(now.year, now.month)
            ),
            "challenges": self._tupled(self._client.get_challenges),
            "favorite_routes": self._tupled(self._client.get_favorite_routes),
            "events": self._tupled(self._client.get_events),
            "achievements": self._client.get_achievements,
            "trophies": self._client.get_trophies,
        }
        values = await asyncio.gather(*(self._section(n, f) for n, f in loaders.items()))
        sections = dict(zip(loaders, values, strict=True))
        return dataclasses.replace(
            RouvySnapshot(profile=profile, fetched_at=dt_util.utcnow()),
            **sections,
        )

    async def _fetch_profile(self) -> UserProfile:
        """Fetch the profile, translating auth failures into a reauth request."""
        try:
            return await self._client.get_user_profile()
        except (RouvyInvalidCredentialsError, RouvyAccountDisabledError) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except RouvyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _section(
        self, name: str, loader: Callable[[], Awaitable[SectionValue]]
    ) -> SectionValue | None:
        """Fetch one optional section, falling back to the previous value on failure."""
        async with self._limit:
            try:
                value = await loader()
            except RouvyError as err:
                previous = self._last_sections.get(name)
                LOGGER.warning(
                    "Could not refresh Rouvy %s (%s); %s",
                    name,
                    err,
                    "keeping previous data" if previous is not None else "it will be unavailable",
                )
                return previous
            self._last_sections[name] = value
            return value

    @staticmethod
    def _tupled[T](
        loader: Callable[[], Awaitable[list[T]]],
    ) -> Callable[[], Awaitable[tuple[T, ...]]]:
        """Wrap a list-returning loader so the snapshot stays immutable."""

        async def load() -> tuple[T, ...]:
            return tuple(await loader())

        return load
