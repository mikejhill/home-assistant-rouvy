"""Realistic Rouvy response bodies: sanitized captures plus encoded synthetic pages."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from rouvy_api.config import Endpoint
from tests.support.turbo_encoder import (
    UNDEFINED_VALUE,
    Deferred,
    EncodedValue,
    Tagged,
    TurboStreamEncoder,
)

FIXTURES_DIR: Final = Path(__file__).resolve().parent.parent / "fixtures"
CAPTURED: Final[dict[str, str]] = {
    Endpoint.USER_SETTINGS: "user-settings-data.txt",
    Endpoint.ZONES: "user-settings-zones-data.txt",
    Endpoint.CONNECTED_APPS: "user-settings-connected-apps-data.txt",
    Endpoint.PROFILE_OVERVIEW: "profile-overview-data.txt",
    "resources/activities-pagination.data": "activities-pagination-data.txt",
}
# Real captures from a test account (no joined events, trophies, or activity), used by parser tests
CAPTURED_EXTRA: Final[dict[str, str]] = {
    Endpoint.ACTIVITY_STATS: "activity-stats-data.txt",
    Endpoint.CHALLENGES: "challenges-data.txt",
    Endpoint.EVENTS: "events-data.txt",
    Endpoint.ACHIEVEMENTS: "achievements-data.txt",
    Endpoint.TROPHIES: "trophies-data.txt",
    Endpoint.FAVORITE_ROUTES: "routes-favourite-data.txt",
}
EVENT_ID: Final = "3f1c2b9a-5d7e-4a1b-9c3d-2e4f6a8b0c1d"
CHALLENGE_SLUG: Final = "october-climb-2026"


class RouvyPayloads:
    """Build response bodies for every endpoint the client uses."""

    def __init__(self, today: date | None = None) -> None:
        self._today = today or datetime.now(UTC).date()

    def captured(self, endpoint: str) -> str:
        """Return a sanitized real capture."""
        name = CAPTURED.get(endpoint) or CAPTURED_EXTRA[endpoint]
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    def all_reads(self) -> dict[str, str]:
        """Return a body for every read endpoint."""
        bodies = {endpoint: self.captured(endpoint) for endpoint in CAPTURED}
        bodies.update(
            {
                Endpoint.ACTIVITY_STATS: self.activity_stats(),
                Endpoint.CHALLENGES: self.challenges(),
                Endpoint.ROUTES: self.routes(),
                Endpoint.FAVORITE_ROUTES: self.favorite_routes(),
                Endpoint.EVENTS: self.events(),
                Endpoint.ACHIEVEMENTS: self.achievements(),
                Endpoint.TROPHIES: self.trophies(),
            }
        )
        return bodies

    # Synthetic pages

    def activity_stats(self) -> str:
        """Return weekly stats where the current week has two rides."""
        monday = self._today - timedelta(days=self._today.weekday())
        weeks: dict[str, EncodedValue] = {}
        for offset in range(-1, 1):
            start = monday + timedelta(weeks=offset)
            current = offset == 0
            weeks[str(offset + 1)] = {
                "weekStart": self._display(start),
                "weekEnd": self._display(start + timedelta(days=7)),
                "activityTypeStats": {
                    "ride": self._type_stats(rides=2 if current else 1),
                    "workout": self._type_stats(rides=1 if current else 0),
                    "event": self._type_stats(rides=0),
                    "outdoor": self._type_stats(rides=0),
                },
            }
        return self.encode({"data": weeks})

    def challenges(self) -> str:
        """Return one active, one completed, and one unregistered challenge."""
        start = datetime(2026, 10, 1, tzinfo=UTC)
        items: list[EncodedValue] = [
            self._challenge(CHALLENGE_SLUG, "October Climb", registered=True, done=False),
            self._challenge("september-distance", "September Distance", registered=True, done=True),
            self._challenge("winter-warmup", "Winter Warmup", registered=False, done=False),
        ]
        page = {"challenges": items, "now": start}
        return self.route_page("routes/_main.challenges.status.$status", page)

    def routes(self) -> str:
        """Return two favorite routes and one other route."""
        items: list[EncodedValue] = [
            self._route(96000, "Col du Galibier", favorite=True, online=12),
            self._route(96001, "Alpe d'Huez", favorite=True, online=30),
            self._route(96002, "Flat Loop", favorite=False, online=4),
        ]
        return self.route_page("routes/_main.routes._index", {"routes": items})

    def favorite_routes(self) -> str:
        """Return the favourites collection with two routes."""
        routes: list[EncodedValue] = [
            self._route(96000, "Col du Galibier", favorite=False, online=12),
            self._route(96001, "Alpe d'Huez", favorite=False, online=30),
        ]
        collection: dict[str, EncodedValue] = {
            "slug": "abc123",
            "name": "My favourite",
            "collectionType": "favourite",
            "itemsCount": 2,
            "routes": routes,
        }
        return self.route_page(
            "routes/_main.routes.collection.$slug", {"routeCollection": collection, "page": 1}
        )

    def events(self) -> str:
        """Return two upcoming events (deliberately out of order)."""
        later = datetime(2026, 10, 20, 17, 0, tzinfo=UTC)
        sooner = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
        joined = self._event(EVENT_ID, "Saturday Morning Ride", sooner, joined=True)
        page: dict[str, EncodedValue] = {
            "featuredEvents": [self._event("b2", "Evening Race", later, joined=False)],
            "joinedEventsPromise": Deferred([joined]),
            "upcomingEventsPromise": Deferred(
                [self._event("b2", "Evening Race", later, joined=False), joined]
            ),
            "finishedEventsPromise": Deferred(
                [self._event("old", "Last Week", sooner - timedelta(days=9), joined=True)]
            ),
        }
        return self.route_page("routes/_main.events._index", page)

    def achievements(self) -> str:
        """Return three achievements, two completed."""
        page: dict[str, EncodedValue] = {
            "achievements": {
                "distanceAchievements": [
                    {"goal": {"isCompleted": True}, "coins": 50, "experience": 100},
                    {"goal": {"isCompleted": False}, "coins": 80, "experience": 150},
                ],
                "workoutsAchievements": [
                    {"goal": {"isCompleted": True}, "coins": 20, "experience": 40},
                ],
            }
        }
        return self.route_page("routes/_main.profile.achievements", page)

    def trophies(self) -> str:
        """Return four trophies."""
        trophies: list[EncodedValue] = [
            {"routeId": f"r{i}", "type": "GOLD", "value": i} for i in range(4)
        ]
        return self.route_page("routes/_main.profile.trophies", {"trophies": trophies})

    # Auth pages

    def login_error(self, message: str, email: str, password: str) -> str:
        """Return the form-error body Rouvy sends for a rejected login."""
        return self.encode(
            {
                "data": {
                    "status": "error",
                    "intent": UNDEFINED_VALUE,
                    "initialValue": {"email": email, "password": password},
                    "error": {"": [message]},
                    "state": UNDEFINED_VALUE,
                    "fields": ["email", "password"],
                }
            }
        )

    def redirect(self, location: str) -> str:
        """Return a single-fetch redirect body."""
        target: dict[str, EncodedValue] = {
            "redirect": location,
            "status": 302,
            "revalidate": False,
            "reload": False,
            "replace": False,
        }
        return self.encode(Tagged("SingleFetchRedirect", (target,)))

    def sign_in_redirect(self, path: str) -> str:
        """Return the redirect Rouvy sends to unauthenticated readers."""
        return self.redirect(
            f"https://account.rouvy.com/sign-in?riders=true&redirectTo=%2F{path.removesuffix('.data')}"
        )

    def action_ok(self) -> str:
        """Return a successful action body."""
        return self.encode({"data": {"status": "success", "ok": True}})

    # Encoding helpers

    def route_page(self, route_id: str, data: dict[str, EncodedValue]) -> str:
        """Wrap page data the way Remix single fetch does, including the layout route."""
        layout: dict[str, EncodedValue] = {
            "onlineFriendsCount": Deferred(1),
            "friendsPromise": Deferred({"data": [], "total": 3}),
        }
        return self.encode(
            {
                "root": {"data": {"locale": "en", "userId": "redacted"}},
                "routes/_main": {"data": layout},
                route_id: {"data": data},
            }
        )

    @staticmethod
    def encode(value: EncodedValue) -> str:
        """Encode a value graph as turbo-stream."""
        return TurboStreamEncoder().encode(value)

    @staticmethod
    def _type_stats(rides: int) -> dict[str, EncodedValue]:
        """Return totals for one activity type."""
        return {
            "distM": 21000.5 * rides,
            "elevM": 310.0 * rides,
            "kCal": 450 * rides,
            "movingTimeSec": 3600 * rides,
            "trainingScore": 55 * rides,
            "activityCount": rides,
            "if": 0.8 if rides else 0,
        }

    @staticmethod
    def _challenge(slug: str, title: str, *, registered: bool, done: bool) -> EncodedValue:
        """Return one challenge."""
        return {
            "id": slug,
            "title": title,
            "state": "FINISHED" if done else "RUNNING",
            "userStatus": "COMPLETED" if done else "IN_PROGRESS",
            "registered": registered,
            "joined": registered,
            "isDone": done,
            "isPast": False,
            "isUpcoming": False,
            "registeredCount": 1200,
            "experience": 500,
            "coins": 100,
            "startDateTime": "2026-10-01T00:00:00.000Z",
            "endDateTime": "2026-10-31T23:59:59.000Z",
        }

    @staticmethod
    def _route(route_id: int, name: str, *, favorite: bool, online: int) -> EncodedValue:
        """Return one route."""
        return {
            "id": route_id,
            "name": name,
            "distanceInMeters": 34200.0,
            "elevationInMeters": 2100.0,
            "estimatedTime": 7200,
            "rating": 4.8,
            "countryCodeISO": "FR",
            "favorite": favorite,
            "onlineCount": online,
        }

    @staticmethod
    def _event(event_id: str, title: str, starts: datetime, *, joined: bool) -> EncodedValue:
        """Return one event in the shape of the events page."""
        return {
            "id": event_id,
            "title": title,
            "type": "RACE",
            "joined": joined,
            "official": True,
            "status": "OFFLINE",
            "startDateTime": starts,
            "registrationsCount": 100,
            "laps": 1,
            "coinsForCompletion": 60,
            "experience": 200,
            "startDateFormatted": starts.strftime("%b %d, %Y, %I:%M %p UTC"),
        }

    @staticmethod
    def _display(day: date) -> str:
        """Format a date the way Rouvy's activity stats do."""
        return day.strftime("%b %d, %Y, 12:00 AM UTC")
