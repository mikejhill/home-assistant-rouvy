#!/usr/bin/env python3
"""Rouvy API client — async CLI for all Rouvy API endpoints.

Usage:
    python -m custom_components.rouvy.api_client <subcommand> [options]

Requires ROUVY_EMAIL and ROUVY_PASSWORD in a .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import sys
from typing import Any

import aiohttp
from dotenv import load_dotenv

from ..api import RouvyAsyncApiClient
from .models import (
    AchievementsSummary,
    Activity,
    ActivitySummary,
    CareerStats,
    Challenge,
    ConnectedApp,
    Event,
    FriendsSummary,
    Route,
    TrainingZones,
    TrophiesSummary,
    UserProfile,
    WeeklyActivityStats,
)
from .parser import parse_response

_LOGGER = logging.getLogger(__name__)

_ZONE_LABELS: list[str] = [
    "Recovery",
    "Endurance",
    "Tempo",
    "Threshold",
    "VO2Max",
    "Anaerobic",
]

_PROFILE_FIELDS: list[str] = [
    "email",
    "username",
    "first_name",
    "last_name",
    "weight_kg",
    "height_cm",
    "units",
    "ftp_watts",
    "ftp_source",
    "max_heart_rate",
    "gender",
    "birth_date",
    "country",
    "timezone",
    "account_privacy",
    "user_id",
]


# ---------------------------------------------------------------------------
# Credentials & logging helpers
# ---------------------------------------------------------------------------


def load_credentials() -> tuple[str, str]:
    """Load email and password from .env file."""
    load_dotenv()
    email: str | None = os.getenv("ROUVY_EMAIL")
    password: str | None = os.getenv("ROUVY_PASSWORD")

    if not email or not password:
        raise ValueError("ROUVY_EMAIL and ROUVY_PASSWORD must be set in .env file")

    return email, password


def _configure_logging(args: argparse.Namespace) -> None:
    log_level = "DEBUG" if args.debug else args.log_level
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _json_out(obj: dict | list) -> None:
    """Print a JSON-serialisable object to stdout."""
    print(json.dumps(obj, indent=2, default=str))


def _json_err(message: str) -> None:
    """Print a JSON error object to stderr."""
    print(json.dumps({"error": message}), file=sys.stderr)


def _json_ok() -> None:
    """Print a JSON success object to stdout."""
    print(json.dumps({"status": "ok"}))


def _as_dict(obj: object) -> dict[str, object] | list[dict[str, object]]:
    """Convert a dataclass instance (or list of them) to a dict."""
    if isinstance(obj, list):
        return [dataclasses.asdict(item) for item in obj]  # ty: ignore[invalid-argument-type]
    return dataclasses.asdict(obj)  # ty: ignore[invalid-argument-type]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _coerce_value(value: str) -> int | float | str:
    """Try to convert a string value to int, then float, else keep as string."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_settings(raw_settings: list[str]) -> dict[str, Any]:
    """Parse a list of KEY=VALUE strings into a dict."""
    updates: dict[str, Any] = {}
    for setting in raw_settings:
        if "=" not in setting:
            msg = f"Invalid format '{setting}'. Use KEY=VALUE format."
            raise ValueError(msg)
        key, value = setting.split("=", 1)
        updates[key] = _coerce_value(value)
    return updates


def _format_profile_field(name: str) -> str:
    """Convert a dataclass field name to a human-readable label."""
    _labels: dict[str, str] = {
        "email": "Email",
        "username": "Username",
        "first_name": "First Name",
        "last_name": "Last Name",
        "weight_kg": "Weight (kg)",
        "height_cm": "Height (cm)",
        "units": "Units",
        "ftp_watts": "FTP (watts)",
        "ftp_source": "FTP Source",
        "max_heart_rate": "Max Heart Rate",
        "gender": "Gender",
        "birth_date": "Birth Date",
        "country": "Country",
        "timezone": "Timezone",
        "account_privacy": "Account Privacy",
        "user_id": "User ID",
    }
    return _labels.get(name, name.replace("_", " ").title())


def _format_time(seconds: int) -> str:
    """Format seconds into h:mm:ss or m:ss."""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    """Add flags shared by all subcommands."""
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut for --log-level DEBUG",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of formatted text",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rouvy API client — async CLI for all Rouvy API endpoints",
    )
    _add_common_flags(parser)

    sub = parser.add_subparsers(dest="subcommand")

    # --- Read subcommands (alphabetical) ---

    sp = sub.add_parser("activities", help="Display recent activities")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_activities)

    sp = sub.add_parser("activity-stats", help="Weekly activity statistics")
    sp.add_argument("--year", type=int, required=True, help="Calendar year")
    sp.add_argument("--month", type=int, required=True, help="Calendar month (1-12)")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_activity_stats)

    sp = sub.add_parser("apps", help="Display connected apps")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_apps)

    sp = sub.add_parser("career", help="Career progression stats")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_career)

    sp = sub.add_parser("challenges", help="List available challenges")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_challenges)

    sp = sub.add_parser("events", help="List upcoming events")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_events)

    sp = sub.add_parser("friends", help="Friends summary")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_friends)

    sp = sub.add_parser("profile", help="Display user profile (default)")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_profile)

    sp = sub.add_parser("raw", help="Fetch raw decoded output for any endpoint")
    sp.add_argument("raw_endpoint", metavar="ENDPOINT", help="API endpoint to fetch")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_raw)

    sp = sub.add_parser("register-challenge", help="Register for a challenge")
    sp.add_argument("--slug", required=True, help="Challenge slug")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_register_challenge)

    sp = sub.add_parser("register-event", help="Register for an event")
    sp.add_argument("--event-id", required=True, help="Event ID")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_register_event)

    sp = sub.add_parser("routes", help="List favorite routes")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_routes)

    # --- Write subcommands (alphabetical) ---

    sp = sub.add_parser("set", help="Update user settings (KEY=VALUE pairs)")
    sp.add_argument(
        "settings",
        nargs="+",
        metavar="KEY=VALUE",
        help="Settings to update (e.g. weight=86 height=178)",
    )
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set)

    sp = sub.add_parser("set-ftp", help="Update FTP")
    sp.add_argument(
        "--source",
        required=True,
        choices=["MANUAL", "ESTIMATED"],
        help="FTP source",
    )
    sp.add_argument("--value", type=int, default=None, help="FTP in watts (required for MANUAL)")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_ftp)

    sp = sub.add_parser("set-height", help="Update height")
    sp.add_argument("--height", type=float, required=True, help="Height in cm")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_height)

    sp = sub.add_parser("set-max-hr", help="Update max heart rate")
    sp.add_argument("--max-hr", type=int, required=True, help="Max heart rate in bpm")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_max_hr)

    sp = sub.add_parser("set-profile", help="Update profile fields")
    sp.add_argument("--username", default=None, help="Display username")
    sp.add_argument("--first-name", default=None, help="First name")
    sp.add_argument("--last-name", default=None, help="Last name")
    sp.add_argument("--team", default=None, help="Team name")
    sp.add_argument("--country", default=None, help="Two-letter country code")
    sp.add_argument(
        "--privacy",
        default=None,
        choices=["PUBLIC", "PRIVATE"],
        help="Account privacy",
    )
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_profile)

    sp = sub.add_parser("set-timezone", help="Update timezone")
    sp.add_argument("--timezone", required=True, help="IANA timezone (e.g. America/New_York)")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_timezone)

    sp = sub.add_parser("set-units", help="Update units")
    sp.add_argument(
        "--units",
        required=True,
        choices=["METRIC", "IMPERIAL"],
        help="Unit system",
    )
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_units)

    sp = sub.add_parser("set-weight", help="Update weight")
    sp.add_argument("--weight", type=float, required=True, help="Weight in kg")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_weight)

    sp = sub.add_parser("set-zones", help="Update zone boundaries")
    sp.add_argument(
        "--type",
        required=True,
        choices=["power", "heartRate"],
        dest="zone_type",
        help="Zone type",
    )
    sp.add_argument(
        "--zones",
        required=True,
        help="Comma-separated zone boundary percentages (e.g. 55,75,90,105,120,150)",
    )
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_set_zones)

    sp = sub.add_parser("unregister-event", help="Unregister from an event")
    sp.add_argument("--event-id", required=True, help="Event ID")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_unregister_event)

    sp = sub.add_parser("zones", help="Display training zones")
    _add_common_flags(sp)
    sp.set_defaults(handler=_cmd_zones)

    args = parser.parse_args()

    # Default to profile when no subcommand is given
    if not hasattr(args, "handler") or args.handler is None:
        args.handler = _cmd_profile

    return args


# ---------------------------------------------------------------------------
# Read-command handlers
# ---------------------------------------------------------------------------


async def _cmd_activities(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    summary: ActivitySummary = await client.async_get_activity_summary()
    activities: list[Activity] = summary.recent_activities

    if args.json_output:
        _json_out(_as_dict(summary))
        return

    print("=" * 70)
    print("RECENT ACTIVITIES")
    print("=" * 70)

    if not activities:
        print("\n  No recent activities found.")
        print("=" * 70)
        return

    print(f"\n  {'Title':<30s} {'Date':<22s} {'Distance':>10s} {'Time':>10s}")
    print(f"  {'-' * 28:<30s} {'-' * 20:<22s} {'-' * 10:>10s} {'-' * 10:>10s}")
    for act in activities:
        date_str = act.start_utc or "—"
        dist_km = act.distance_m / 1000.0
        dist_str = f"{dist_km:.1f} km"
        time_str = _format_time(act.moving_time_seconds)
        title = (act.title[:27] + "...") if len(act.title) > 30 else act.title
        print(f"  {title:<30s} {date_str:<22s} {dist_str:>10s} {time_str:>10s}")
    print("=" * 70)


async def _cmd_activity_stats(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    stats: list[WeeklyActivityStats] = await client.async_get_activity_stats(args.year, args.month)

    if args.json_output:
        _json_out(_as_dict(stats))
        return

    print("=" * 70)
    print(f"ACTIVITY STATS — {args.year}/{args.month:02d}")
    print("=" * 70)

    if not stats:
        print("\n  No activity stats found for this period.")
        print("=" * 70)
        return

    for week in stats:
        print(f"\n  Week: {week.week_start} → {week.week_end}")
        for activity_type in ("ride", "workout", "event", "outdoor"):
            ts = getattr(week, activity_type)
            if ts.activity_count > 0:
                dist_km = ts.distance_m / 1000.0
                print(
                    f"    {activity_type.capitalize():<10s}: "
                    f"{ts.activity_count} activities, "
                    f"{dist_km:.1f} km, "
                    f"{_format_time(ts.moving_time_seconds)}, "
                    f"{ts.calories:.0f} cal"
                )
    print("=" * 70)


async def _cmd_apps(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    apps: list[ConnectedApp] = await client.async_get_connected_apps()

    if args.json_output:
        _json_out(_as_dict(apps))
        return

    print("=" * 70)
    print("CONNECTED APPS")
    print("=" * 70)
    print(f"\nFound {len(apps)} app integrations:\n")
    print(f"  {'Status':<12s} {'Name':<25s} {'Provider'}")
    print(f"  {'-' * 10:<12s} {'-' * 23:<25s} {'-' * 20}")
    for app in apps:
        icon = "✓" if app.status.lower() == "connected" else "✗"
        print(f"  {icon} {app.status:<10s} {app.name:<25s} {app.provider_id}")
    print("=" * 70)


async def _cmd_career(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    career: CareerStats = await client.async_get_career()
    achievements: AchievementsSummary = await client.async_get_achievements()
    trophies: TrophiesSummary = await client.async_get_trophies()

    if args.json_output:
        career_dict = _as_dict(career)
        assert isinstance(career_dict, dict)  # single dataclass, never list
        combined = {
            **career_dict,
            "achievements": _as_dict(achievements),
            "trophies": _as_dict(trophies),
        }
        _json_out(combined)
        return

    print("=" * 70)
    print("CAREER STATS")
    print("=" * 70)
    print(f"  Level              : {career.level}")
    print(f"  Experience         : {career.experience_points:,} XP")
    earned = achievements.earned_achievements
    total = achievements.total_achievements
    print(f"  Achievements       : {earned}/{total}")
    print(f"  Trophies           : {trophies.total_trophies}")
    print("=" * 70)


async def _cmd_challenges(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    challenges: list[Challenge] = await client.async_get_challenges()

    if args.json_output:
        _json_out(_as_dict(challenges))
        return

    print("=" * 70)
    print("AVAILABLE CHALLENGES")
    print("=" * 70)

    if not challenges:
        print("\n  No challenges available.")
        print("=" * 70)
        return

    print(f"\n  {'Title':<35s} {'State':<12s} {'Registered':<12s} {'Dates'}")
    print(f"  {'-' * 33:<35s} {'-' * 10:<12s} {'-' * 10:<12s} {'-' * 25}")
    for ch in challenges:
        reg = "Yes" if ch.registered else "No"
        dates = f"{ch.start_date_time[:10]} → {ch.end_date_time[:10]}"
        title = (ch.title[:32] + "...") if len(ch.title) > 35 else ch.title
        print(f"  {title:<35s} {ch.state:<12s} {reg:<12s} {dates}")
    print("=" * 70)


async def _cmd_events(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    events: list[Event] = await client.async_get_events()

    if args.json_output:
        _json_out(_as_dict(events))
        return

    print("=" * 70)
    print("UPCOMING EVENTS")
    print("=" * 70)

    if not events:
        print("\n  No upcoming events.")
        print("=" * 70)
        return

    print(f"\n  {'Title':<35s} {'Type':<12s} {'Start':<22s} {'Reg'}")
    print(f"  {'-' * 33:<35s} {'-' * 10:<12s} {'-' * 20:<22s} {'-' * 5}")
    for ev in events:
        reg = "Yes" if ev.registered else "No"
        title = (ev.title[:32] + "...") if len(ev.title) > 35 else ev.title
        print(f"  {title:<35s} {ev.event_type:<12s} {ev.start_date_time:<22s} {reg}")
    print("=" * 70)


async def _cmd_friends(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    friends: FriendsSummary = await client.async_get_friends()

    if args.json_output:
        _json_out(_as_dict(friends))
        return

    print("=" * 70)
    print("FRIENDS SUMMARY")
    print("=" * 70)
    print(f"  Total Friends  : {friends.total_friends}")
    print(f"  Online Friends : {friends.online_friends}")
    print("=" * 70)


async def _cmd_profile(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    profile: UserProfile = await client.async_get_user_profile()

    if args.json_output:
        _json_out(_as_dict(profile))
        return

    print("=" * 70)
    print("USER PROFILE")
    print("=" * 70)
    for field_name in _PROFILE_FIELDS:
        value = getattr(profile, field_name)
        if value is None:
            continue
        label = _format_profile_field(field_name)
        print(f"{label:25s}: {value}")
    print("=" * 70)


async def _cmd_raw(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    endpoint: str = args.raw_endpoint
    # Use the client's internal _request to fetch raw text
    text: str = await client._request("GET", endpoint)
    decoded = parse_response(text)

    if args.json_output:
        _json_out(decoded)
        return

    print(f"Fetching: {endpoint}")
    print(f"Response: {len(text):,} bytes")
    print("\n" + "=" * 70)
    print("RAW DECODED RESPONSE")
    print("=" * 70)
    output = json.dumps(decoded, indent=2, default=str)[:5000]
    print(output)
    if len(json.dumps(decoded, indent=2, default=str)) > 5000:
        print("\n... (truncated)")
    print("=" * 70)


async def _cmd_routes(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    routes: list[Route] = await client.async_get_favorite_routes()

    if args.json_output:
        _json_out(_as_dict(routes))
        return

    print("=" * 70)
    print("FAVORITE ROUTES")
    print("=" * 70)

    if not routes:
        print("\n  No favorite routes found.")
        print("=" * 70)
        return

    print(f"\n  {'Name':<35s} {'Distance':>10s} {'Elevation':>10s} {'Country'}")
    print(f"  {'-' * 33:<35s} {'-' * 10:>10s} {'-' * 10:>10s} {'-' * 7}")
    for route in routes:
        dist_km = route.distance_m / 1000.0
        name = (route.name[:32] + "...") if len(route.name) > 35 else route.name
        print(f"  {name:<35s} {dist_km:>9.1f}km {route.elevation_m:>9.0f}m {route.country_code}")
    print("=" * 70)


async def _cmd_zones(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    zones: TrainingZones = await client.async_get_training_zones()

    if args.json_output:
        _json_out(_as_dict(zones))
        return

    print("=" * 70)
    print("TRAINING ZONES")
    print("=" * 70)

    if zones.ftp_watts:
        print(f"\n  FTP: {zones.ftp_watts} watts")
    if zones.max_heart_rate:
        print(f"  Max HR: {zones.max_heart_rate} bpm")

    pz = zones.power_zone_values or zones.power_zone_defaults
    if pz:
        print("\nPower Zones (% FTP):")
        for idx, val in enumerate(pz):
            label = _ZONE_LABELS[idx] if idx < len(_ZONE_LABELS) else f"Zone {idx + 1}"
            print(f"  Zone {idx + 1} ({label:12s}): {val}%")

    hr = zones.hr_zone_values or zones.hr_zone_defaults
    if hr:
        print("\nHeart Rate Zones (% Max HR):")
        for idx, val in enumerate(hr):
            label = _ZONE_LABELS[idx] if idx < len(_ZONE_LABELS) else f"Zone {idx + 1}"
            print(f"  Zone {idx + 1} ({label:12s}): {val}%")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Write-command handlers
# ---------------------------------------------------------------------------


async def _cmd_register_challenge(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    success: bool = await client.async_register_challenge(args.slug)

    if args.json_output:
        _json_out({"status": "ok", "registered": success})
        return

    if success:
        print(f"✓ Registered for challenge: {args.slug}")
    else:
        print(f"✗ Failed to register for challenge: {args.slug}")


async def _cmd_register_event(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    success: bool = await client.async_register_event(args.event_id)

    if args.json_output:
        _json_out({"status": "ok", "registered": success})
        return

    if success:
        print(f"✓ Registered for event: {args.event_id}")
    else:
        print(f"✗ Failed to register for event: {args.event_id}")


async def _cmd_set(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    updates = _parse_settings(args.settings)

    await client.async_update_user_settings(updates)

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Settings updated: {updates}")
    print("\nFetching updated profile...")
    profile: UserProfile = await client.async_get_user_profile()
    update_keys = set(updates.keys())

    print("\n" + "=" * 70)
    print("UPDATED USER PROFILE")
    print("=" * 70)
    for field_name in _PROFILE_FIELDS:
        value = getattr(profile, field_name)
        if value is None:
            continue
        label = _format_profile_field(field_name)
        is_updated = any(
            uk in field_name.lower() or field_name.lower() in uk.lower() for uk in update_keys
        )
        marker = " ← UPDATED" if is_updated else ""
        print(f"{label:25s}: {value}{marker}")
    print("=" * 70)


async def _cmd_set_ftp(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_ftp(args.source, args.value)

    if args.json_output:
        _json_ok()
        return

    value_str = f" ({args.value}W)" if args.value is not None else ""
    print(f"✓ FTP updated: source={args.source}{value_str}")


async def _cmd_set_height(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_user_settings({"height": args.height})

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Height updated to {args.height} cm")


async def _cmd_set_max_hr(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_max_heart_rate(args.max_hr)

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Max heart rate updated to {args.max_hr} bpm")


async def _cmd_set_profile(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    # Build profile updates from provided flags
    updates: dict[str, Any] = {}
    if args.username is not None:
        updates["username"] = args.username
    if args.first_name is not None:
        updates["firstName"] = args.first_name
    if args.last_name is not None:
        updates["lastName"] = args.last_name
    if args.team is not None:
        updates["team"] = args.team
    if args.country is not None:
        updates["countryIsoCode"] = args.country

    if not updates and args.privacy is None:
        msg = "No profile fields specified. Use --username, --first-name, etc."
        raise ValueError(msg)

    if updates:
        await client.async_update_user_profile(updates)
    if args.privacy is not None:
        await client.async_update_user_social(args.privacy)

    if args.json_output:
        _json_ok()
        return

    changed = {**updates}
    if args.privacy is not None:
        changed["privacy"] = args.privacy
    print(f"✓ Profile updated: {changed}")


async def _cmd_set_timezone(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_timezone(args.timezone)

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Timezone updated to {args.timezone}")


async def _cmd_set_units(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_user_settings({"units": args.units})

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Units updated to {args.units}")


async def _cmd_set_weight(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    await client.async_update_user_settings({"weight": args.weight})

    if args.json_output:
        _json_ok()
        return

    print(f"✓ Weight updated to {args.weight} kg")


async def _cmd_set_zones(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    zone_values = [int(v.strip()) for v in args.zones.split(",")]
    await client.async_update_zones(args.zone_type, zone_values)

    if args.json_output:
        _json_ok()
        return

    print(f"✓ {args.zone_type} zones updated to {zone_values}")


async def _cmd_unregister_event(client: RouvyAsyncApiClient, args: argparse.Namespace) -> None:
    success: bool = await client.async_unregister_event(args.event_id)

    if args.json_output:
        _json_out({"status": "ok", "unregistered": success})
        return

    if success:
        print(f"✓ Unregistered from event: {args.event_id}")
    else:
        print(f"✗ Failed to unregister from event: {args.event_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _async_main(args: argparse.Namespace) -> None:
    """Create an aiohttp session, authenticate, and dispatch the command."""
    email, password = load_credentials()
    async with aiohttp.ClientSession() as session:
        client = RouvyAsyncApiClient(email, password, session)
        await args.handler(client, args)


def main() -> None:
    """Parse arguments, configure logging, and dispatch the CLI command."""
    args = _parse_args()
    _configure_logging(args)

    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass
    except ValueError as exc:
        if args.json_output:
            _json_err(str(exc))
            sys.exit(1)
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        if args.json_output:
            _json_err(str(exc))
            sys.exit(1)
        print(f"Error: {exc}", file=sys.stderr)
        _LOGGER.debug("Traceback:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
