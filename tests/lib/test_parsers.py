"""Tests for RouvyParser against sanitized real captures and synthetic pages."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from rouvy_api import Endpoint, Payload, RouvyResponseError, ZoneType
from rouvy_api.parsers import RouvyParser
from tests.support.rouvy_payloads import EVENT_ID, RouvyPayloads
from tests.support.turbo_encoder import Deferred, EncodedValue, TurboStreamEncoder


class Pages:
    """Helpers to build payloads."""

    @staticmethod
    def captured(payloads: RouvyPayloads, endpoint: str) -> Payload:
        """Return a parsed real capture."""
        return Payload.parse(payloads.captured(endpoint))

    @staticmethod
    def encode(value: EncodedValue) -> Payload:
        """Return a parsed synthetic payload."""
        return Payload.parse(TurboStreamEncoder().encode(value))


@pytest.fixture
def parser() -> RouvyParser:
    """A parser."""
    return RouvyParser()


class TestRealCaptures:
    """Values parsed from real Rouvy responses."""

    def test_user_profile(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """The profile has identity, body metrics, and training settings."""
        profile = parser.user_profile(Pages.captured(payloads, Endpoint.USER_SETTINGS))

        assert profile.email == "rider@example.com"
        assert profile.username == "test-rider"
        assert profile.units == "METRIC"
        assert profile.weight_kg == 85.0
        assert profile.height_cm == 178.0
        assert profile.ftp_source == "ESTIMATED"
        assert profile.estimated_ftp_watts == 165
        assert profile.effective_ftp_watts == 165
        assert profile.max_heart_rate == 190
        assert profile.birth_date == date(1990, 1, 1)
        assert profile.account_privacy == "PUBLIC"

    def test_training_zones(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Zones come from the zones page config."""
        zones = parser.training_zones(Pages.captured(payloads, Endpoint.ZONES))

        assert zones.power_zones == (55, 75, 90, 105, 120, 150)
        assert zones.heart_rate_zones == (60, 65, 75, 82, 89, 94)
        assert zones.max_heart_rate == 190
        assert zones.estimated_ftp_watts == 165

    def test_connected_apps(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Connected apps include active and available providers."""
        apps = parser.connected_apps(Pages.captured(payloads, Endpoint.CONNECTED_APPS))

        assert len(apps) == 17
        assert sorted(a.provider_id for a in apps if a.is_active) == ["garminconnect", "strava"]

    def test_profile_overview(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """The overview has activities, totals, career, and friends."""
        overview = parser.profile_overview(Pages.captured(payloads, Endpoint.PROFILE_OVERVIEW))

        assert len(overview.recent_activities) == 10
        assert overview.recent_activities[0].title == "Faistos | Crete"
        assert overview.recent_activities[0].started_at == datetime(
            2026, 2, 3, 0, 35, 7, tzinfo=UTC
        )
        assert overview.year_totals is not None
        assert overview.year_totals.distance_m == pytest.approx(89431.219)
        assert overview.month_totals is not None
        assert overview.career is not None
        assert (overview.career.experience_points, overview.career.level) == (1067, 5)
        assert overview.friends is not None
        assert (overview.friends.total, overview.friends.online) == (0, 0)

    def test_activities_pagination(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """The pagination resource lists activities."""
        activities = parser.activities(
            Pages.captured(payloads, "resources/activities-pagination.data")
        )

        assert len(activities) == 10
        assert all(a.distance_m > 0 for a in activities)


class TestSyntheticPages:
    """Pages built with the encoder."""

    def test_weekly_stats_sorted(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Weeks are sorted by start date."""
        weeks = parser.weekly_activity_stats(Payload.parse(payloads.activity_stats()))

        assert [w.week_start for w in weeks] == [date(2026, 9, 28), date(2026, 10, 5)]
        assert weeks[1].ride.activity_count == 2
        assert weeks[1].contains(date(2026, 10, 10))

    def test_challenges(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Challenges parse with registration state."""
        challenges = parser.challenges(Payload.parse(payloads.challenges()))

        assert [c.is_active for c in challenges] == [True, False, False]
        assert challenges[1].is_done

    def test_routes(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Routes parse with favorites."""
        routes = parser.routes(Payload.parse(payloads.routes()))

        assert [r.route_id for r in routes if r.favorite] == [96000, 96001]

    def test_events_sorted(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Events from a deferred promise are sorted soonest first."""
        events = parser.events(Payload.parse(payloads.events()))

        assert [e.event_id for e in events] == [EVENT_ID, "b2"]
        assert events[0].coins == 60
        assert events[0].experience == 200

    def test_events_with_missing_start(self, parser: RouvyParser) -> None:
        """Events without a start time sort last and fall back to top-level fields."""
        page = Pages.encode(
            {
                "upcomingEvents": [
                    {"id": "no-start", "title": "TBD", "experience": 5},
                    {"id": "early", "startDateTime": "2026-10-11T08:00:00Z"},
                ]
            }
        )

        events = parser.events(page)

        assert [e.event_id for e in events] == ["early", "no-start"]
        assert events[1].experience == 5

    def test_achievements_and_trophies(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Achievements and trophies are counted."""
        achievements = parser.achievements(Payload.parse(payloads.achievements()))
        trophies = parser.trophies(Payload.parse(payloads.trophies()))

        assert (achievements.total, achievements.earned) == (3, 2)
        assert (achievements.coins_earned, achievements.experience_earned) == (70, 140)
        assert trophies.total == 4

    def test_friends_from_layout(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Friend counts come from layout promises when present."""
        friends = parser.friends(Payload.parse(payloads.routes()))

        assert (friends.total, friends.online) == (3, 1)


class TestEdgeCases:
    """Missing or unusual data."""

    def test_missing_profile_raises(self, parser: RouvyParser) -> None:
        """A page without userProfile is an error, since the profile is required."""
        with pytest.raises(RouvyResponseError, match="userProfile"):
            parser.user_profile(Pages.encode({"data": {}}))

    def test_profile_without_email(self, parser: RouvyParser) -> None:
        """An email-less profile parses with defaults."""
        profile = parser.user_profile(
            Pages.encode({"userProfile": {"userId": "u1"}, "email": "nope"})
        )

        assert profile.user_id == "u1"
        assert profile.email is None
        assert profile.units == "METRIC"
        assert profile.display_name is None

    def test_zones_fall_back_to_profile(self, parser: RouvyParser) -> None:
        """Without a zones config, zones come from the profile summary."""
        page = Pages.encode(
            {
                "userProfile": {
                    "ftp": 250,
                    "maxHeartRate": 185,
                    "zones": {
                        "power": {"values": None, "defaultValues": [55, 75]},
                        "heartRate": {"values": [60, 70], "defaultValues": [61, 71]},
                    },
                }
            }
        )

        zones = parser.training_zones(page)

        assert zones.ftp_watts == 250
        assert zones.zones_for(ZoneType.POWER) == (55, 75)
        assert zones.zones_for(ZoneType.HEART_RATE) == (60, 70)

    def test_zones_empty(self, parser: RouvyParser) -> None:
        """No zone data at all yields empty zones."""
        zones = parser.training_zones(Pages.encode({"data": {}}))

        assert zones.power_zones == ()
        assert zones.ftp_watts is None

    def test_zones_config_with_numbers(self, parser: RouvyParser) -> None:
        """Zone lists of plain numbers are accepted."""
        page = Pages.encode({"config": {"power": {"value": 200, "zones": [50, 60]}}})

        zones = parser.training_zones(page)

        assert zones.power_zones == (50, 60)
        assert zones.heart_rate_zones == ()

    def test_connected_apps_skip_unnamed(self, parser: RouvyParser) -> None:
        """Providers without an id are skipped; missing names fall back to the id."""
        page = Pages.encode({"activeProviders": [{"status": "active"}, {"providerId": "x"}]})

        apps = parser.connected_apps(page)

        assert [(a.provider_id, a.name, a.status) for a in apps] == [("x", "x", "unknown")]

    @pytest.mark.parametrize(
        ("career", "expected"),
        [
            pytest.param(
                [
                    {
                        "historyData": {"currentPoints": 100},
                        "careerLevels": [
                            {"sublevels": [{"points": 0}, {"points": 90}, {"points": 300}]}
                        ],
                    }
                ],
                (100, 2),
                id="list",
            ),
            pytest.param([], None, id="empty-list"),
            pytest.param({"careerLevels": []}, None, id="no-history"),
        ],
    )
    def test_career_shapes(
        self, parser: RouvyParser, career: EncodedValue, expected: tuple[int, int] | None
    ) -> None:
        """The careerData payload may be a list or an object."""
        overview = parser.profile_overview(Pages.encode({"careerData": career}))

        result = overview.career
        assert (None if result is None else (result.experience_points, result.level)) == expected

    @pytest.mark.parametrize(
        ("page", "expected"),
        [
            pytest.param({"friendsCount": 7}, (7, 0), id="count-only"),
            pytest.param(
                {"friends": [{"online": True}, {"status": "RIDING"}, {"status": "offline"}, {}]},
                (4, 2),
                id="list",
            ),
            pytest.param({"onlineFriendsCount": Deferred(2)}, (0, 2), id="online-only"),
            pytest.param({"nothing": 1}, None, id="absent"),
        ],
    )
    def test_friend_sources(
        self, parser: RouvyParser, page: dict[str, EncodedValue], expected: tuple[int, int] | None
    ) -> None:
        """Friend counts combine whichever sources a page has."""
        friends = parser.profile_overview(Pages.encode(page)).friends

        assert (None if friends is None else (friends.total, friends.online)) == expected

    def test_period_totals_absent(self, parser: RouvyParser) -> None:
        """Missing statistics give no period totals."""
        overview = parser.profile_overview(Pages.encode({"statisticsPromise": {"yearly": []}}))

        assert overview.year_totals is not None
        assert overview.year_totals.distance_m == 0.0
        assert overview.month_totals is None

    def test_empty_collections(self, parser: RouvyParser) -> None:
        """Pages without the expected keys yield empty results."""
        page = Pages.encode({"data": {}})

        assert parser.challenges(page) == []
        assert parser.routes(page) == []
        assert parser.events(page) == []
        assert parser.weekly_activity_stats(page) == []
        assert parser.achievements(page).total == 0
        assert parser.trophies(page).total == 0
        assert parser.friends(page).total == 0

    def test_weekly_stats_missing_types(self, parser: RouvyParser) -> None:
        """Weeks with missing type totals or dates still parse."""
        page = Pages.encode({"data": {"0": {"activityTypeStats": {"ride": {"distM": 1000}}}}})

        weeks = parser.weekly_activity_stats(page)

        assert weeks[0].ride.distance_m == 1000
        assert weeks[0].workout.distance_m == 0
        assert not weeks[0].contains(date(2026, 1, 1))


class TestMoreRealCaptures:
    """Endpoints captured from a live test account (no joined events, trophies, or rides)."""

    def test_challenges(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Available challenges parse with titles and start dates."""
        challenges = parser.challenges(Pages.captured(payloads, Endpoint.CHALLENGES))

        assert len(challenges) == 24
        assert all(c.title and c.starts_at for c in challenges)
        assert not any(c.is_active for c in challenges)

    def test_events(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Joined, upcoming, and featured events are merged without duplicates."""
        events = parser.events(Pages.captured(payloads, Endpoint.EVENTS))

        assert len(events) == 20
        assert len({e.event_id for e in events}) == 20
        assert all(e.starts_at for e in events)
        assert not any(e.registered for e in events)
        assert events == sorted(
            events, key=lambda e: e.starts_at or datetime.max.replace(tzinfo=UTC)
        )

    def test_favorite_routes(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """The favourites collection lists the rider's favorite routes."""
        routes = parser.favorite_routes(Pages.captured(payloads, Endpoint.FAVORITE_ROUTES))

        assert [r.route_id for r in routes] == [275570, 277442, 275576]
        assert all(r.favorite and r.distance_m > 0 for r in routes)

    def test_achievements_and_trophies(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Achievement categories are counted; an account without trophies has none."""
        achievements = parser.achievements(Pages.captured(payloads, Endpoint.ACHIEVEMENTS))
        trophies = parser.trophies(Pages.captured(payloads, Endpoint.TROPHIES))

        assert (achievements.total, achievements.earned) == (44, 0)
        assert trophies.total == 0

    def test_weekly_stats_display_dates(self, parser: RouvyParser, payloads: RouvyPayloads) -> None:
        """Display-format week bounds become inclusive Monday-to-Sunday dates."""
        weeks = parser.weekly_activity_stats(Pages.captured(payloads, Endpoint.ACTIVITY_STATS))

        assert [(w.week_start, w.week_end) for w in weeks[:2]] == [
            (date(2026, 9, 28), date(2026, 10, 4)),
            (date(2026, 10, 5), date(2026, 10, 11)),
        ]
        assert len(weeks) == 5
        assert weeks[1].contains(date(2026, 10, 11))
        assert not weeks[1].contains(date(2026, 10, 12))
