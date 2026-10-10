"""Convert decoded Rouvy payloads into typed models.

Parsers locate data by key name (breadth-first) rather than by Remix route id, so
they keep working when Rouvy renames or nests routes.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Final

from custom_components.rouvy.rouvy_api.exceptions import RouvyResponseError
from custom_components.rouvy.rouvy_api.models import (
    AchievementsSummary,
    Activity,
    ActivityTypeTotals,
    CareerProgress,
    Challenge,
    ConnectedApp,
    Event,
    FriendsSummary,
    PeriodTotals,
    ProfileOverview,
    Route,
    TrainingZones,
    TrophiesSummary,
    UnitSystem,
    UserProfile,
    WeeklyActivityStats,
)
from custom_components.rouvy.rouvy_api.payload import Fields, Payload

_JOINED_EVENTS_KEY: Final = "joinedEventsPromise"
# Joined events first, so their registration state wins when an event is listed twice
_EVENT_LIST_KEYS: Final = (
    _JOINED_EVENTS_KEY,
    "upcomingEventsPromise",
    "featuredEvents",
    "events",
    "upcomingEvents",
)
_DAYS_PER_WEEK: Final = 7
_ROUTE_LIST_KEYS: Final = ("routes", "routeOverviews")
_FRIEND_LIST_KEYS: Final = ("friends", "friendList", "friendsList")
_ONLINE_MARKERS: Final = frozenset({"online", "active", "riding"})


class RouvyParser:
    """Stateless conversions from Payload to models."""

    def user_profile(self, payload: Payload) -> UserProfile:
        """Parse ``user-settings.data``.

        Raises:
            RouvyResponseError: If the payload contains no user profile.
        """
        profile = payload.find_fields("userProfile")
        if profile is None:
            msg = "Response did not contain a userProfile object"
            raise RouvyResponseError(msg)
        email = payload.find("email")
        return UserProfile(
            user_id=profile.text("firebaseUid") or profile.text("userId"),
            email=email if isinstance(email, str) and "@" in email else None,
            username=profile.text("userName"),
            first_name=profile.text("firstName"),
            last_name=profile.text("lastName"),
            gender=profile.text("gender"),
            birth_date=profile.day("birthDate"),
            country=profile.text("countryIsoCode"),
            timezone=profile.text("timezone"),
            language=profile.text("language"),
            account_privacy=profile.text("accountPrivacy"),
            units=profile.text("units") or UnitSystem.METRIC,
            weight_kg=profile.number("weight"),
            height_cm=profile.number("height"),
            ftp_watts=profile.integer("ftp"),
            estimated_ftp_watts=profile.integer("estimateFtp"),
            ftp_source=profile.text("ftpSource"),
            max_heart_rate=profile.integer("maxHeartRate"),
        )

    def training_zones(self, payload: Payload) -> TrainingZones:
        """Parse ``user-settings/zones.data``."""
        config = payload.find_fields("config")
        power = config.mapping("power") if config else None
        heart = config.mapping("heartRate") if config else None
        if power is None and heart is None:
            return self._zones_from_profile(payload)
        return TrainingZones(
            ftp_watts=power.integer("value") if power else None,
            estimated_ftp_watts=power.integer("estimateValue") if power else None,
            max_heart_rate=heart.integer("value") if heart else None,
            power_zones=self._zone_values(power, "zones"),
            power_zone_defaults=self._zone_values(power, "defaultZones"),
            heart_rate_zones=self._zone_values(heart, "zones"),
            heart_rate_zone_defaults=self._zone_values(heart, "defaultZones"),
        )

    def connected_apps(self, payload: Payload) -> list[ConnectedApp]:
        """Parse ``user-settings/connected-apps.data``."""
        apps: list[ConnectedApp] = []
        for key in ("activeProviders", "availableProviders"):
            for item in payload.find_records(key) or []:
                provider_id = item.text("providerId")
                if provider_id is None:
                    continue
                metadata = item.mapping("tokenMetadata")
                apps.append(
                    ConnectedApp(
                        provider_id=provider_id,
                        name=item.text("name") or provider_id,
                        status=item.text("status") or "unknown",
                        upload_mode=item.text("uploadMode"),
                        permissions=tuple(metadata.strings("permissions")) if metadata else (),
                    )
                )
        return apps

    def profile_overview(self, payload: Payload) -> ProfileOverview:
        """Parse ``profile/overview.data`` (activities, totals, career, friends)."""
        activities = [
            self._activity(item)
            for item in payload.find_records("activities") or []
            if item.text("id") is not None
        ]
        statistics = payload.find_fields("statisticsPromise")
        return ProfileOverview(
            recent_activities=tuple(activities),
            year_totals=self._period_totals(statistics, "yearly"),
            month_totals=self._period_totals(statistics, "monthly"),
            career=self._career(payload),
            friends=self._friends(payload),
        )

    def activities(self, payload: Payload) -> list[Activity]:
        """Parse an activity list such as ``resources/activities-pagination.data``."""
        return [
            self._activity(item)
            for item in payload.find_records("activities") or []
            if item.text("id") is not None
        ]

    def weekly_activity_stats(self, payload: Payload) -> list[WeeklyActivityStats]:
        """Parse ``resources/activity-stats.data``, ordered by week start."""
        weeks = [
            WeeklyActivityStats(
                week_start=week.day("weekStart"),
                week_end=self._inclusive_week_end(week),
                ride=self._type_totals(week, "ride"),
                workout=self._type_totals(week, "workout"),
                event=self._type_totals(week, "event"),
                outdoor=self._type_totals(week, "outdoor"),
            )
            for week in payload.objects_with("activityTypeStats")
        ]
        return sorted(weeks, key=lambda w: (w.week_start is None, w.week_start))

    def challenges(self, payload: Payload) -> list[Challenge]:
        """Parse ``challenges/status/available.data``."""
        return [
            Challenge(
                challenge_id=item.text("id") or item.text("slug") or "",
                title=item.text("title"),
                state=item.text("state"),
                user_status=item.text("userStatus"),
                registered=item.flag("registered"),
                is_done=item.flag("isDone"),
                is_past=item.flag("isPast"),
                is_upcoming=item.flag("isUpcoming"),
                registered_count=item.integer("registeredCount") or 0,
                experience=item.integer("experience") or 0,
                coins=item.integer("coins") or 0,
                starts_at=item.timestamp("startDateTime"),
                ends_at=item.timestamp("endDateTime"),
            )
            for item in payload.find_records("challenges") or []
        ]

    def routes(self, payload: Payload) -> list[Route]:
        """Parse the first route list on a page such as ``routes.data``."""
        return [self._route(item) for item in self._first_list(payload, _ROUTE_LIST_KEYS)]

    def favorite_routes(self, payload: Payload) -> list[Route]:
        """Parse ``routes/collection/favourite.data``; every route there is a favorite."""
        collection = payload.find_fields("routeCollection")
        items = collection.records("routes") if collection else []
        return [dataclasses.replace(self._route(item), favorite=True) for item in items]

    def events(self, payload: Payload) -> list[Event]:
        """Parse ``events.data``: joined, upcoming, and featured events, de-duplicated."""
        events: dict[str, Event] = {}
        for key in _EVENT_LIST_KEYS:
            for item in payload.find_records(key) or []:
                event = self._event(item, joined_list=key == _JOINED_EVENTS_KEY)
                if event.event_id and event.event_id not in events:
                    events[event.event_id] = event
        return sorted(events.values(), key=lambda e: (e.starts_at is None, e.starts_at))

    def achievements(self, payload: Payload) -> AchievementsSummary:
        """Parse ``profile/achievements.data``."""
        categories = payload.find_fields("achievements")
        if categories is None:
            return AchievementsSummary()
        total = earned = coins = experience = 0
        for category in categories.raw:
            for item in categories.records(category):
                total += 1
                goal = item.mapping("goal")
                if goal is not None and goal.flag("isCompleted"):
                    earned += 1
                    coins += item.integer("coins") or 0
                    experience += item.integer("experience") or 0
        return AchievementsSummary(
            total=total, earned=earned, coins_earned=coins, experience_earned=experience
        )

    def trophies(self, payload: Payload) -> TrophiesSummary:
        """Parse ``profile/trophies.data``."""
        value = payload.find("trophies")
        return TrophiesSummary(total=len(value) if isinstance(value, list) else 0)

    def friends(self, payload: Payload) -> FriendsSummary:
        """Parse friend counts from any page that carries them."""
        return self._friends(payload) or FriendsSummary()

    # Internals

    @staticmethod
    def _route(item: Fields) -> Route:
        """Build a Route from one list element."""
        return Route(
            route_id=item.integer("id") or 0,
            name=item.text("name"),
            distance_m=item.number("distanceInMeters") or 0.0,
            elevation_m=item.number("elevationInMeters") or 0.0,
            estimated_time_s=item.integer("estimatedTime") or 0,
            rating=item.number("rating"),
            country_code=item.text("countryCodeISO"),
            favorite=item.flag("favorite"),
            online_count=item.integer("onlineCount") or 0,
        )

    @staticmethod
    def _event(item: Fields, *, joined_list: bool) -> Event:
        """Build an Event from one list element (current or legacy shape)."""
        session = item.mapping("session") or item
        return Event(
            event_id=item.text("id") or "",
            title=item.text("originalTitle") or item.text("title"),
            event_type=item.text("type"),
            starts_at=session.timestamp("startDateTime") or item.timestamp("startDateTime"),
            registrations=item.integer("registrationsCount") or item.integer("capacity") or 0,
            registered=joined_list or item.flag("joined") or item.flag("registered"),
            official=item.flag("official"),
            coins=session.integer("coinsForCompletion") or 0,
            experience=session.integer("eventExperience") or item.integer("experience") or 0,
        )

    @staticmethod
    def _inclusive_week_end(week: Fields) -> date | None:
        """Return the last day of a week; Rouvy reports the following Monday at midnight."""
        start, end = week.day("weekStart"), week.day("weekEnd")
        if start is not None and end is not None and (end - start).days == _DAYS_PER_WEEK:
            return end - timedelta(days=1)
        return end

    @staticmethod
    def _zone_values(zone: Fields | None, key: str) -> tuple[int, ...]:
        """Return zone boundaries from a list of ``{"value": n}`` objects or numbers."""
        if zone is None:
            return ()
        records = zone.records(key)
        if records:
            return tuple(v for v in (r.integer("value") for r in records) if v is not None)
        return tuple(round(v) for v in zone.numbers(key))

    def _zones_from_profile(self, payload: Payload) -> TrainingZones:
        """Fall back to the zone summary embedded in the user profile."""
        profile = payload.find_fields("userProfile")
        zones = profile.mapping("zones") if profile else None
        power = zones.mapping("power") if zones else None
        heart = zones.mapping("heartRate") if zones else None
        return TrainingZones(
            ftp_watts=profile.integer("ftp") if profile else None,
            estimated_ftp_watts=profile.integer("estimateFtp") if profile else None,
            max_heart_rate=profile.integer("maxHeartRate") if profile else None,
            power_zones=self._zone_values(power, "values"),
            power_zone_defaults=self._zone_values(power, "defaultValues"),
            heart_rate_zones=self._zone_values(heart, "values"),
            heart_rate_zone_defaults=self._zone_values(heart, "defaultValues"),
        )

    @staticmethod
    def _activity(item: Fields) -> Activity:
        """Build an Activity from one list element."""
        total = item.mapping("total") or Fields({})
        return Activity(
            activity_id=item.text("id") or "",
            title=item.text("title"),
            started_at=item.timestamp("startUTC"),
            training_type=item.text("training"),
            distance_m=total.number("distM") or 0.0,
            elevation_m=total.number("elevM") or 0.0,
            moving_time_s=total.integer("movingTimeSec") or 0,
            calories_kcal=total.number("kCal"),
            training_score=item.number("trainingScore"),
            intensity_factor=total.number("if"),
        )

    @staticmethod
    def _period_totals(statistics: Fields | None, key: str) -> PeriodTotals | None:
        """Convert ``[{type, value}]`` statistics into PeriodTotals."""
        if statistics is None or not statistics.has(key):
            return None
        values = {r.text("type"): r.number("value") or 0.0 for r in statistics.records(key)}
        return PeriodTotals(
            duration_s=values.get("Duration", 0.0),
            distance_m=values.get("Distance", 0.0),
            ascent_m=values.get("Ascent", 0.0),
        )

    @staticmethod
    def _type_totals(week: Fields, key: str) -> ActivityTypeTotals:
        """Return one activity type's weekly totals."""
        types = week.mapping("activityTypeStats")
        raw = types.mapping(key) if types else None
        if raw is None:
            return ActivityTypeTotals()
        return ActivityTypeTotals(
            distance_m=raw.number("distM") or 0.0,
            elevation_m=raw.number("elevM") or 0.0,
            calories_kcal=raw.number("kCal") or 0.0,
            moving_time_s=raw.integer("movingTimeSec") or 0,
            training_score=raw.number("trainingScore") or 0.0,
            activity_count=raw.integer("activityCount") or 0,
        )

    def _career(self, payload: Payload) -> CareerProgress | None:
        """Compute XP and level from ``careerData`` (object or single-element list)."""
        raw = payload.find("careerData")
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        career = Fields.wrap(raw)
        history = career.mapping("historyData") if career else None
        if career is None or history is None:
            return None
        points = history.integer("currentPoints") or 0
        thresholds = [
            sub.integer("points") or 0
            for level in career.records("careerLevels")
            for sub in level.records("sublevels")
        ]
        return CareerProgress(
            experience_points=points, level=sum(1 for t in thresholds if points >= t)
        )

    def _friends(self, payload: Payload) -> FriendsSummary | None:
        """Combine friend totals and online counts from wherever they appear."""
        promise = payload.find_fields("friendsPromise")
        total = promise.integer("total") if promise else None
        if total is None:
            count = payload.find("friendsCount")
            total = count if isinstance(count, int) and not isinstance(count, bool) else None
        listed = self._first_list(payload, _FRIEND_LIST_KEYS)
        if total is None and listed:
            total = len(listed)
        online = payload.find("onlineFriendsCount")
        if not isinstance(online, int) or isinstance(online, bool):
            online = sum(1 for f in listed if self._is_online(f)) if listed else None
        if total is None and online is None:
            return None
        return FriendsSummary(total=total or 0, online=online or 0)

    @staticmethod
    def _is_online(friend: Fields) -> bool:
        """Return True when a friend entry reports an online status."""
        if friend.flag("online"):
            return True
        status = friend.text("status")
        return status is not None and status.lower() in _ONLINE_MARKERS

    @staticmethod
    def _first_list(payload: Payload, keys: tuple[str, ...]) -> list[Fields]:
        """Return the first list found under any of the keys."""
        for key in keys:
            records = payload.find_records(key)
            if records is not None:
                return records
        return []
