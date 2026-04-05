"""Parser for Rouvy API responses using turbo-stream format.

Rouvy uses the turbo-stream format from Remix (https://github.com/jacob-ebey/turbo-stream),
which is a streaming data format that supports more types than JSON and uses indexed
references to deduplicate repeated values.

Format characteristics:
- Main array with alternating keys and values
- Indexed references: {"_N": value} where N points to the key at index N in the array
- Special types:
  - Dates: ["D", timestamp_ms]
  - Promises: ["P", reference_id]
  - Negative indices: -5 represents undefined, -7 represents null
- Multi-line responses: First line is main data, subsequent lines resolve promises
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import (
        ActivitySummary,
        ActivityTypeStats,
        CareerStats,
        Challenge,
        ConnectedApp,
        Event,
        FriendsSummary,
        Route,
        TrainingZones,
        UserProfile,
        WeeklyActivityStats,
    )

_LOGGER = logging.getLogger(__name__)

# Special sentinel values
UNDEFINED = object()  # Represents JavaScript undefined
NULL = None  # Represents JavaScript null


class TurboStreamDecoder:
    """Decoder for turbo-stream formatted responses."""

    def __init__(self) -> None:
        self.index_map: dict[int, Any] = {}
        self.promise_values: dict[int, Any] = {}

    def decode(self, response_text: str) -> dict[str, Any] | list[Any] | Any:
        """Decode a turbo-stream formatted response.

        Args:
            response_text: Raw response text (may be multi-line)

        Returns:
            Decoded data structure
        """
        lines = response_text.strip().split("\n")
        main_data = json.loads(lines[0])

        # Parse promise resolutions from subsequent lines
        for line in lines[1:]:
            line = line.strip()
            if line and line.startswith("P"):
                self._parse_promise_line(line)

        # Build index map from the main array
        if isinstance(main_data, list):
            for i, item in enumerate(main_data):
                self.index_map[i] = item

        # Decode the main structure
        return self._decode_value(main_data)

    def _parse_promise_line(self, line: str) -> None:
        """Parse promise resolution lines like 'P132:-5' or 'P134:[...]'."""
        try:
            # Format: P<id>:<value>
            if ":" in line:
                parts = line.split(":", 1)
                promise_id = int(parts[0][1:])  # Remove 'P' prefix
                value_str = parts[1]

                # Try to parse as JSON
                try:
                    value = json.loads(value_str)
                    self.promise_values[promise_id] = value
                except json.JSONDecodeError:
                    # Might be a simple value like -5
                    if value_str.lstrip("-").isdigit():
                        self.promise_values[promise_id] = int(value_str)
                    else:
                        _LOGGER.warning("Could not parse promise value: %s", value_str)
        except Exception as e:
            _LOGGER.warning("Error parsing promise line '%s': %s", line, e)

    def _decode_value(self, value: Any, resolve_int_as_index: bool = False) -> Any:
        """Recursively decode a value, resolving references and special types.

        Args:
            value: The value to decode
            resolve_int_as_index: If True, treat integers as index references to resolve
        """
        # Handle special numeric sentinels
        if isinstance(value, int):
            if value == -5:
                return UNDEFINED
            if value == -7:
                return NULL
            # Only resolve as index if explicitly requested (for indexed object values)
            if (
                resolve_int_as_index
                and value in self.index_map
                and value not in getattr(self, "_resolving", set())
            ):
                # Avoid infinite recursion
                if not hasattr(self, "_resolving"):
                    self._resolving = set()
                self._resolving.add(value)
                result = self._decode_value(self.index_map[value], resolve_int_as_index=False)
                self._resolving.discard(value)
                return result
            return value

        # Handle arrays
        if isinstance(value, list):
            # Check for special array formats
            if len(value) == 2:
                # Date format: ["D", timestamp_ms]
                if value[0] == "D" and isinstance(value[1], (int, float)):
                    try:
                        return datetime.fromtimestamp(value[1] / 1000)
                    except ValueError, OSError:
                        _LOGGER.warning("Invalid timestamp: %s", value[1])
                        return value

                # Promise reference: ["P", id]
                if value[0] == "P" and isinstance(value[1], int):
                    promise_id = value[1]
                    if promise_id in self.promise_values:
                        return self._decode_value(
                            self.promise_values[promise_id], resolve_int_as_index=False
                        )
                    # Promise not yet resolved
                    return f"<Promise:{promise_id}>"

            # Regular array - decode each element (don't resolve ints as indices)
            return [self._decode_value(item, resolve_int_as_index=False) for item in value]

        # Handle objects with indexed references
        if isinstance(value, dict):
            result = {}
            for key, val in value.items():
                if key.startswith("_"):
                    # This is an indexed reference for the KEY
                    try:
                        index = int(key[1:])
                        # Look up the actual key name
                        if index in self.index_map:
                            actual_key = self.index_map[index]
                            if isinstance(actual_key, str):
                                # VALUE of indexed keys should be resolved as index references
                                decoded_val = self._decode_value(val, resolve_int_as_index=True)
                                result[actual_key] = decoded_val
                            else:
                                # Key itself needs decoding
                                decoded_key = self._decode_value(
                                    actual_key, resolve_int_as_index=False
                                )
                                if isinstance(decoded_key, str):
                                    decoded_val = self._decode_value(val, resolve_int_as_index=True)
                                    result[decoded_key] = decoded_val
                                else:
                                    result[key] = self._decode_value(
                                        val, resolve_int_as_index=False
                                    )
                        else:
                            result[key] = self._decode_value(val, resolve_int_as_index=False)
                    except ValueError:
                        result[key] = self._decode_value(val, resolve_int_as_index=False)
                else:
                    # Regular key - value is literal
                    result[key] = self._decode_value(val, resolve_int_as_index=False)
            return result

        # Return other types as-is
        return value

    def extract_data_section(self, decoded: Any, path: str = "root.data") -> dict[str, Any]:
        """Extract a specific data section from the decoded structure.

        Args:
            decoded: Decoded turbo-stream data
            path: Dot-separated path to the data section (default: "root.data")

        Returns:
            Extracted data section or empty dict if not found
        """
        if not isinstance(decoded, dict):
            return {}

        parts = path.split(".")
        current = decoded

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                _LOGGER.debug("Path '%s' not found in decoded data", path)
                return {}

        return current if isinstance(current, dict) else {}


def parse_response(response_text: str) -> dict[str, Any] | list[Any] | Any:
    """Parse a Rouvy API response in turbo-stream format.

    Args:
        response_text: Raw response text

    Returns:
        Decoded data structure
    """
    decoder = TurboStreamDecoder()
    return decoder.decode(response_text)


def extract_user_profile(response_text: str) -> dict[str, Any]:
    """Extract user profile fields from user-settings response.

    Args:
        response_text: Raw user-settings.data response

    Returns:
        Dict with user profile fields
    """
    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)

    # Find the userProfile object in the decoded array
    user_data = {}
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    # First pass: find top-level email
    for i in range(len(array_data)):
        if array_data[i] == "email" and i + 1 < len(array_data):
            next_val = array_data[i + 1]
            if isinstance(next_val, str) and "@" in next_val:
                user_data["email"] = next_val
            break

    # Second pass: find userProfile object
    for i in range(len(array_data)):
        if array_data[i] == "userProfile" and i + 1 < len(array_data):
            profile_obj = array_data[i + 1]
            if isinstance(profile_obj, dict):
                # Extract fields from userProfile object
                if "userName" in profile_obj:
                    user_data["username"] = profile_obj["userName"]
                if "userId" in profile_obj:
                    user_data["user_id"] = profile_obj["userId"]
                if "firstName" in profile_obj and profile_obj["firstName"] is not UNDEFINED:
                    user_data["first_name"] = profile_obj["firstName"]
                if "lastName" in profile_obj and profile_obj["lastName"] is not UNDEFINED:
                    user_data["last_name"] = profile_obj["lastName"]
                if "ftp" in profile_obj:
                    user_data["ftp_watts"] = profile_obj["ftp"]
                if "ftpSource" in profile_obj:
                    val = profile_obj["ftpSource"]
                    if isinstance(val, str):
                        user_data["ftp_source"] = val
                if "weight" in profile_obj:
                    user_data["weight_kg"] = profile_obj["weight"]
                if "height" in profile_obj:
                    user_data["height_cm"] = profile_obj["height"]
                if "gender" in profile_obj:
                    user_data["gender"] = profile_obj["gender"]
                if "maxHeartRate" in profile_obj:
                    user_data["max_heart_rate"] = profile_obj["maxHeartRate"]
                if "countryIsoCode" in profile_obj:
                    user_data["country"] = profile_obj["countryIsoCode"]
                if "timezone" in profile_obj:
                    user_data["timezone"] = profile_obj["timezone"]
                if "units" in profile_obj:
                    user_data["units"] = profile_obj["units"]
                if "accountPrivacy" in profile_obj:
                    val = profile_obj["accountPrivacy"]
                    if isinstance(val, str):
                        user_data["account_privacy"] = val
                if "birthDate" in profile_obj:
                    birth_date = profile_obj["birthDate"]
                    if isinstance(birth_date, datetime):
                        user_data["birth_date"] = birth_date.date().isoformat()
            break

    return user_data


# ---------------------------------------------------------------------------
# Typed model extraction functions
# ---------------------------------------------------------------------------


def _resolve_index(value: Any, index_map: dict[int, Any], depth: int = 0) -> Any:
    """Resolve an integer index reference from the turbo-stream index map.

    Handles nested dicts and lists recursively, with a depth limit to
    prevent infinite loops. Simple values (str, int, float) resolved from
    the index map are returned directly without further resolution.
    """
    if depth > 6:
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == -5 or value == -7:
            return None
        if value in index_map:
            resolved = index_map[value]
            # Simple values: return directly, don't recurse (avoids
            # accidental double-resolution when a resolved value like 55
            # also happens to be a valid index in the map).
            if isinstance(resolved, (str, int, float, bool)) or resolved is None:
                return resolved
            # Complex values: recurse to resolve nested references
            return _resolve_index(resolved, index_map, depth + 1)
        return value
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if k.startswith("_"):
                try:
                    ki = int(k[1:])
                    actual_key = index_map.get(ki, k)
                    if isinstance(actual_key, str):
                        result[actual_key] = _resolve_index(v, index_map, depth + 1)
                except ValueError:
                    pass
            else:
                result[k] = _resolve_index(v, index_map, depth + 1)
        return result
    if isinstance(value, list):
        return [_resolve_index(item, index_map, depth + 1) for item in value]
    return value


def _find_key_value(decoded: list[Any], key: str) -> Any:
    """Find a key in the decoded array and return its adjacent value."""
    for i in range(len(decoded)):
        if decoded[i] == key and i + 1 < len(decoded):
            return decoded[i + 1]
    return None


def _safe_int(value: Any) -> int:
    """Convert a value to int, returning 0 for non-numeric values."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _safe_float(value: Any) -> float:
    """Convert a value to float, returning 0.0 for non-numeric values."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0


def _safe_str(value: Any) -> str:
    """Convert a value to str, returning '' for sentinel objects."""
    if value is None or value is UNDEFINED:
        return ""
    if isinstance(value, str):
        return value
    return ""


def extract_user_profile_model(response_text: str) -> UserProfile:
    """Extract a typed UserProfile from a user-settings.data response."""
    from .models import UserProfile

    raw = extract_user_profile(response_text)
    birth_date_val = raw.get("birth_date")
    birth_date = None
    if isinstance(birth_date_val, str):
        try:
            from datetime import date as date_cls

            birth_date = date_cls.fromisoformat(birth_date_val)
        except ValueError:
            pass

    return UserProfile(
        email=raw.get("email", ""),
        username=raw.get("username", ""),
        first_name=raw.get("first_name", ""),
        last_name=raw.get("last_name", ""),
        weight_kg=_safe_float(raw.get("weight_kg", 0)),
        height_cm=_safe_float(raw.get("height_cm", 0)),
        units=raw.get("units", "METRIC"),
        ftp_watts=_safe_int(raw.get("ftp_watts", 0)),
        ftp_source=raw.get("ftp_source", ""),
        max_heart_rate=_safe_int(raw.get("max_heart_rate")) or None,
        gender=raw.get("gender"),
        birth_date=birth_date,
        country=raw.get("country"),
        timezone=raw.get("timezone"),
        account_privacy=raw.get("account_privacy"),
        user_id=raw.get("user_id"),
    )


def extract_training_zones_model(response_text: str) -> TrainingZones:
    """Extract typed TrainingZones from a user-settings/zones.data response."""
    from .models import TrainingZones

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    ftp_watts = 0
    max_heart_rate = 0
    power_values: list[int] = []
    power_defaults: list[int] = []
    hr_values: list[int] = []
    hr_defaults: list[int] = []

    # Extract FTP and max HR from userProfile
    profile_obj = _find_key_value(array_data, "userProfile")
    if isinstance(profile_obj, dict):
        ftp_watts = _safe_int(profile_obj.get("ftp", 0))
        max_heart_rate = _safe_int(profile_obj.get("maxHeartRate", 0))

    # Extract zones
    zones_obj = _find_key_value(array_data, "zones")
    if isinstance(zones_obj, dict):
        # Power zones
        power = zones_obj.get("power")
        if isinstance(power, dict):
            raw_vals = power.get("values")
            raw_defs = power.get("defaultValues")
            if isinstance(raw_vals, list):
                power_values = [_safe_int(_resolve_index(v, decoder.index_map)) for v in raw_vals]
            if isinstance(raw_defs, list):
                power_defaults = [_safe_int(_resolve_index(v, decoder.index_map)) for v in raw_defs]

        # Heart rate zones
        hr = zones_obj.get("heartRate")
        if isinstance(hr, dict):
            raw_vals = hr.get("values")
            raw_defs = hr.get("defaultValues")
            if isinstance(raw_vals, list):
                hr_values = [_safe_int(_resolve_index(v, decoder.index_map)) for v in raw_vals]
            if isinstance(raw_defs, list):
                hr_defaults = [_safe_int(_resolve_index(v, decoder.index_map)) for v in raw_defs]

    return TrainingZones(
        ftp_watts=ftp_watts,
        max_heart_rate=max_heart_rate,
        power_zone_values=power_values,
        power_zone_defaults=power_defaults,
        hr_zone_values=hr_values,
        hr_zone_defaults=hr_defaults,
    )


def extract_connected_apps_model(response_text: str) -> list[ConnectedApp]:
    """Extract typed ConnectedApp list from a connected-apps.data response."""
    from .models import ConnectedApp

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []
    apps: list[ConnectedApp] = []

    for key in ("activeProviders", "availableProviders"):
        raw_list = _find_key_value(array_data, key)
        if not isinstance(raw_list, list):
            continue
        for item in raw_list:
            resolved = _resolve_index(item, decoder.index_map)
            if not isinstance(resolved, dict):
                continue
            permissions: list[str] = []
            meta = resolved.get("tokenMetadata")
            if isinstance(meta, dict):
                perms = meta.get("permissions")
                if isinstance(perms, list):
                    permissions = [str(p) for p in perms if isinstance(p, str)]

            apps.append(
                ConnectedApp(
                    provider_id=_safe_str(resolved.get("providerId")),
                    name=_safe_str(resolved.get("name")),
                    status=_safe_str(resolved.get("status")),
                    upload_mode=_safe_str(resolved.get("uploadMode")) or None,
                    description=_safe_str(resolved.get("description")) or None,
                    logo_path=_safe_str(resolved.get("logoPath")) or None,
                    permissions=permissions,
                )
            )

    return apps


def extract_activities_model(response_text: str) -> ActivitySummary:
    """Extract typed ActivitySummary from a profile/overview.data response."""
    from .models import Activity, ActivitySummary

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []
    activities: list[Activity] = []

    raw_list = _find_key_value(array_data, "activities")
    if isinstance(raw_list, list):
        for item in raw_list:
            resolved = _resolve_index(item, decoder.index_map)
            if not isinstance(resolved, dict):
                continue

            total = resolved.get("total", {})
            if not isinstance(total, dict):
                total = {}

            # intensity_factor: only accept numeric values
            if_val = total.get("if")
            intensity_factor = float(if_val) if isinstance(if_val, (int, float)) else None

            activities.append(
                Activity(
                    activity_id=_safe_str(resolved.get("id")),
                    title=_safe_str(resolved.get("title")),
                    start_utc=_safe_str(resolved.get("startUTC")) or None,
                    training_type=_safe_str(resolved.get("training")),
                    distance_m=_safe_float(total.get("distM", 0)),
                    elevation_m=_safe_float(total.get("elevM", 0)),
                    moving_time_seconds=_safe_int(total.get("movingTimeSec", 0)),
                    intensity_factor=intensity_factor,
                )
            )

    return ActivitySummary(recent_activities=activities)


def extract_activity_stats_model(response_text: str) -> list[WeeklyActivityStats]:
    """Extract typed WeeklyActivityStats from a resources/activity-stats.data response.

    The response is a POST endpoint that returns a dict keyed by week index
    (0, 1, 2, ...) with each value containing weekly stats broken down by
    activity type (ride, workout, event, outdoor).
    """
    from .models import WeeklyActivityStats

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)

    # The parsed data is a flat list: [refmap, key0, val0, key1, val1, ...]
    # For activity-stats, the first value (index 2) is the weekly data dict
    weeks_data: dict[str, Any] = {}
    if isinstance(decoded, list) and len(decoded) > 2:
        candidate = decoded[2]
        if isinstance(candidate, dict):
            weeks_data = candidate

    result: list[WeeklyActivityStats] = []
    for week_key in sorted(weeks_data.keys(), key=lambda k: _safe_int(k)):
        week = weeks_data[week_key]
        if not isinstance(week, dict):
            continue

        type_stats = week.get("activityTypeStats", {})
        if not isinstance(type_stats, dict):
            type_stats = {}

        result.append(
            WeeklyActivityStats(
                week_start=_safe_str(week.get("weekStart")),
                week_end=_safe_str(week.get("weekEnd")),
                ride=_parse_activity_type_stats(type_stats.get("ride")),
                workout=_parse_activity_type_stats(type_stats.get("workout")),
                event=_parse_activity_type_stats(type_stats.get("event")),
                outdoor=_parse_activity_type_stats(type_stats.get("outdoor")),
            )
        )

    return result


def _parse_activity_type_stats(raw: Any) -> ActivityTypeStats:
    """Parse a single activity type stats dict into a typed model."""
    from .models import ActivityTypeStats

    if not isinstance(raw, dict):
        return ActivityTypeStats()

    return ActivityTypeStats(
        distance_m=_safe_float(raw.get("distM", 0)),
        elevation_m=_safe_float(raw.get("elevM", 0)),
        calories=_safe_float(raw.get("kCal", 0)),
        moving_time_seconds=_safe_int(raw.get("movingTimeSec", 0)),
        intensity_factor=_safe_float(raw.get("if", 0)),
        training_score=_safe_float(raw.get("trainingScore", 0)),
        activity_count=_safe_int(raw.get("activityCount", 0)),
    )


def extract_challenges_model(response_text: str) -> list[Challenge]:
    """Extract typed Challenge list from a challenges/status/available.data response.

    The response is a turbo-stream flat list containing a "challenges" key
    whose value is a list of challenge dicts.
    """
    from .models import Challenge

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    challenges: list[Challenge] = []
    raw_list = _find_key_value(array_data, "challenges")
    if not isinstance(raw_list, list):
        return challenges

    for item in raw_list:
        resolved = _resolve_index(item, decoder.index_map)
        if not isinstance(resolved, dict):
            continue

        raw_segments = resolved.get("segments")
        segments: list[Any] = raw_segments if isinstance(raw_segments, list) else []

        challenges.append(
            Challenge(
                id=_safe_str(resolved.get("id")),
                user_status=_safe_str(resolved.get("userStatus")),
                state=_safe_str(resolved.get("state")),
                registered_count=_safe_int(resolved.get("registeredCount", 0)),
                registered=bool(resolved.get("registered", False)),
                title=_safe_str(resolved.get("title")),
                logo=_safe_str(resolved.get("logo")),
                experience=_safe_int(resolved.get("experience", 0)),
                coins=_safe_int(resolved.get("coins", 0)),
                start_date_time=_safe_str(resolved.get("startDateTime")),
                end_date_time=_safe_str(resolved.get("endDateTime")),
                is_past=bool(resolved.get("isPast", False)),
                is_upcoming=bool(resolved.get("isUpcoming", False)),
                is_done=bool(resolved.get("isDone", False)),
                segments=segments,
            )
        )

    return challenges


def extract_routes_model(response_text: str) -> list[Route]:
    """Extract typed Route list from a routes.data response.

    The response is a turbo-stream flat list containing a key like
    "routes" or "routeOverviews" whose value is a list of route dicts.
    """
    from .models import Route

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    routes: list[Route] = []
    raw_list = _find_key_value(array_data, "routes")
    if not isinstance(raw_list, list):
        raw_list = _find_key_value(array_data, "routeOverviews")
    if not isinstance(raw_list, list):
        return routes

    for item in raw_list:
        resolved = _resolve_index(item, decoder.index_map)
        if not isinstance(resolved, dict):
            continue

        # Get route_id from the raw item to avoid index map collisions
        # for small integer values like 1 or 2.
        raw_id = item.get("id", 0) if isinstance(item, dict) else resolved.get("id", 0)

        routes.append(
            Route(
                route_id=_safe_int(raw_id),
                name=_safe_str(resolved.get("name")),
                distance_m=_safe_float(resolved.get("distanceInMeters", 0)),
                elevation_m=_safe_float(resolved.get("elevationInMeters", 0)),
                estimated_time_seconds=_safe_int(resolved.get("estimatedTime", 0)),
                rating=_safe_float(resolved.get("rating", 0)),
                country_code=_safe_str(resolved.get("countryCodeISO")),
                favorite=bool(resolved.get("favorite", False)),
                completed_distance_m=_safe_float(resolved.get("completedDistanceMeters", 0)),
                online_count=_safe_int(resolved.get("onlineCount", 0)),
                coins_for_completion=_safe_int(resolved.get("coinsForCompletion", 0)),
            )
        )

    return routes


def extract_events_model(response_text: str) -> list[Event]:
    """Extract typed Event list from an events.data response.

    The response is a turbo-stream flat list containing event data under
    keys like "events", "upcomingEvents", or "eventSessions".
    """
    from .models import Event

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    events: list[Event] = []
    raw_list = None
    for key in ("events", "upcomingEvents", "eventSessions"):
        raw_list = _find_key_value(array_data, key)
        if isinstance(raw_list, list):
            break

    if not isinstance(raw_list, list):
        return events

    for item in raw_list:
        resolved = _resolve_index(item, decoder.index_map)
        if not isinstance(resolved, dict):
            continue

        # Session-level fields may be nested under "session" or at top level
        session = resolved.get("session", resolved)
        if isinstance(session, dict):
            coins = _safe_int(session.get("coinsForCompletion", 0))
            xp = _safe_int(session.get("eventExperience", resolved.get("experience", 0)))
            start_dt = _safe_str(session.get("startDateTime", resolved.get("startDateTime", "")))
        else:
            coins = _safe_int(resolved.get("coinsForCompletion", 0))
            xp = _safe_int(resolved.get("eventExperience", resolved.get("experience", 0)))
            start_dt = _safe_str(resolved.get("startDateTime", ""))

        events.append(
            Event(
                event_id=_safe_str(resolved.get("id")),
                title=_safe_str(resolved.get("originalTitle", resolved.get("title", ""))),
                event_type=_safe_str(resolved.get("type", "")),
                start_date_time=start_dt,
                capacity=_safe_int(resolved.get("capacity", 0)),
                registered=bool(resolved.get("registered", False)),
                official=bool(resolved.get("official", False)),
                coins_for_completion=coins,
                experience=xp,
                laps=_safe_int(resolved.get("laps", 0)),
            )
        )

    return events


def extract_career_model(response_text: str) -> CareerStats:
    """Extract typed CareerStats from a profile/career.data response.

    This is speculative — the actual response keys are unknown because the
    HAR capture returned empty text. We try several likely key names and
    fall back to defaults when nothing matches.
    """
    from .models import CareerStats

    if not response_text or not response_text.strip():
        return CareerStats()

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    # Try to find a nested career/stats object first
    raw: dict[str, Any] | None = None
    for key in ("career", "stats", "careerStats", "userCareer"):
        candidate = _find_key_value(array_data, key)
        if isinstance(candidate, dict):
            raw = _resolve_index(candidate, decoder.index_map)
            if isinstance(raw, dict):
                break
            raw = None
        elif isinstance(candidate, int) and candidate in decoder.index_map:
            resolved = _resolve_index(candidate, decoder.index_map)
            if isinstance(resolved, dict):
                raw = resolved
                break

    def _pick_int(*keys: str) -> int:
        """Return the first non-None int found in raw or the flat array."""
        if raw:
            for k in keys:
                val = raw.get(k)
                if val is not None:
                    return _safe_int(val)
        for k in keys:
            val = _find_key_value(array_data, k)
            if val is not None:
                return _safe_int(val)
        return 0

    def _pick_float(*keys: str) -> float:
        """Return the first non-None float found in raw or the flat array."""
        if raw:
            for k in keys:
                val = raw.get(k)
                if val is not None:
                    return _safe_float(val)
        for k in keys:
            val = _find_key_value(array_data, k)
            if val is not None:
                return _safe_float(val)
        return 0.0

    return CareerStats(
        total_distance_m=_pick_float("totalDistance", "totalDistM"),
        total_elevation_m=_pick_float("totalElevation", "totalElevM"),
        total_time_seconds=_pick_int("totalTime", "totalTimeSec"),
        total_activities=_pick_int("totalActivities", "activityCount"),
        total_achievements=_pick_int("achievements", "achievementCount"),
        total_trophies=_pick_int("trophies", "trophyCount"),
        experience_points=_pick_int("xp", "experiencePoints"),
        level=_pick_int("level"),
        coins=_pick_int("coins"),
    )


def extract_friends_model(response_text: str) -> FriendsSummary:
    """Extract a FriendsSummary from a friends.data response.

    Searches for known keys that may contain a friends list, counts
    the total entries, and counts those with an online/status indicator.
    """
    from .models import FriendsSummary

    if not response_text or not response_text.strip():
        return FriendsSummary()

    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)
    array_data: list[Any] = decoded if isinstance(decoded, list) else []

    friends_list: list[Any] | None = None
    for key in ("friends", "friendList", "friendsList"):
        candidate = _find_key_value(array_data, key)
        if isinstance(candidate, list):
            friends_list = candidate
            break

    if not friends_list:
        return FriendsSummary()

    total = len(friends_list)
    online = 0
    for item in friends_list:
        resolved = _resolve_index(item, decoder.index_map)
        if not isinstance(resolved, dict):
            continue
        status = resolved.get("status") or resolved.get("online")
        if status in (True, "online", "active"):
            online += 1

    return FriendsSummary(total_friends=total, online_friends=online)
