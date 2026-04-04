#!/usr/bin/env python3
"""
Rouvy API client - Command-line interface for making API calls.

Supports both subcommands (profile, zones, apps, activities, set, raw)
and legacy flags (--endpoint, --set, --raw) for backward compatibility.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv

from . import (
    Activity,
    ActivitySummary,
    ApiResponseError,
    ConnectedApp,
    RouvyClient,
    RouvyConfig,
    TrainingZones,
    UserProfile,
    extract_user_profile,
    parse_response,
)

LOGGER = logging.getLogger(__name__)

_ZONE_LABELS: list[str] = [
    "Recovery",
    "Endurance",
    "Tempo",
    "Threshold",
    "VO2Max",
    "Anaerobic",
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


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    """Add --debug and --log-level flags shared by all subcommands."""
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level for the client",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut for --log-level DEBUG",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rouvy API client - Fetch and parse API endpoints",
    )

    # Legacy flags (kept for backward compatibility)
    parser.add_argument(
        "--endpoint",
        "-e",
        default=None,
        help="(legacy) API endpoint to call",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        default=False,
        help="(legacy) Show raw decoded response instead of formatted output",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        dest="legacy_set",
        help=(
            "(legacy) Update a user setting (can be used multiple times). "
            "Example: --set weight=86 --set height=178"
        ),
    )
    _add_common_flags(parser)

    # Subcommands
    sub = parser.add_subparsers(dest="subcommand")

    # profile
    sp_profile = sub.add_parser("profile", help="Display user profile (default)")
    _add_common_flags(sp_profile)

    # zones
    sp_zones = sub.add_parser("zones", help="Display training zones")
    _add_common_flags(sp_zones)

    # apps
    sp_apps = sub.add_parser("apps", help="Display connected apps")
    _add_common_flags(sp_apps)

    # activities
    sp_activities = sub.add_parser("activities", help="Display recent activities")
    _add_common_flags(sp_activities)

    # set KEY=VALUE ...
    sp_set = sub.add_parser("set", help="Update user settings")
    sp_set.add_argument(
        "settings",
        nargs="+",
        metavar="KEY=VALUE",
        help="Settings to update (e.g. weight=86 height=178)",
    )
    _add_common_flags(sp_set)

    # raw ENDPOINT
    sp_raw = sub.add_parser("raw", help="Show raw decoded output for any endpoint")
    sp_raw.add_argument(
        "raw_endpoint",
        metavar="ENDPOINT",
        help="API endpoint to fetch",
    )
    _add_common_flags(sp_raw)

    return parser.parse_args()


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


def _parse_settings(raw_settings: list[str]) -> dict[str, Any] | None:
    """Parse a list of KEY=VALUE strings into a dict.  Returns None on error."""
    updates: dict[str, Any] = {}
    for setting in raw_settings:
        if "=" not in setting:
            print(f"Error: Invalid format '{setting}'. Use KEY=VALUE format.")
            return None
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
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_profile(client: RouvyClient) -> None:
    profile: UserProfile = client.get_user_profile()
    print("=" * 70)
    print("USER PROFILE")
    print("=" * 70)
    for field_name in [
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
    ]:
        value = getattr(profile, field_name)
        if value is None:
            continue
        label = _format_profile_field(field_name)
        print(f"{label:25s}: {value}")
    print("=" * 70)


def _cmd_zones(client: RouvyClient) -> None:
    zones: TrainingZones = client.get_training_zones()
    print("=" * 70)
    print("TRAINING ZONES")
    print("=" * 70)

    if zones.ftp_watts:
        print(f"\n  FTP: {zones.ftp_watts} watts")
    if zones.max_heart_rate:
        print(f"  Max HR: {zones.max_heart_rate} bpm")

    # Power zones
    pz = zones.power_zone_values or zones.power_zone_defaults
    if pz:
        print("\nPower Zones (% FTP):")
        for idx, val in enumerate(pz):
            label = _ZONE_LABELS[idx] if idx < len(_ZONE_LABELS) else f"Zone {idx + 1}"
            print(f"  Zone {idx + 1} ({label:12s}): {val}%")

    # Heart-rate zones
    hr = zones.hr_zone_values or zones.hr_zone_defaults
    if hr:
        print("\nHeart Rate Zones (% Max HR):")
        for idx, val in enumerate(hr):
            label = _ZONE_LABELS[idx] if idx < len(_ZONE_LABELS) else f"Zone {idx + 1}"
            print(f"  Zone {idx + 1} ({label:12s}): {val}%")

    print("=" * 70)


def _cmd_apps(client: RouvyClient) -> None:
    apps: list[ConnectedApp] = client.get_connected_apps()
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


def _cmd_activities(client: RouvyClient) -> None:
    summary: ActivitySummary = client.get_activity_summary()
    activities: list[Activity] = summary.recent_activities
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


def _cmd_set(client: RouvyClient, settings: list[str]) -> None:
    updates = _parse_settings(settings)
    if updates is None:
        return

    print(f"Updating user settings: {updates}")
    response = client.update_user_settings(updates)
    print(f"Response: {response.status_code}")

    if response.status_code < 300:
        print("✓ Settings updated successfully")
        print("\nFetching updated settings...")
        profile: UserProfile = client.get_user_profile()
        update_keys = set(updates.keys())

        print("\n" + "=" * 70)
        print("UPDATED USER PROFILE")
        print("=" * 70)
        for field_name in [
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
        ]:
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


def _cmd_raw(client: RouvyClient, endpoint: str) -> None:
    print(f"Fetching: {endpoint}")
    response = client.get(endpoint)
    print(f"Response: {response.status_code} ({len(response.text):,} bytes)")
    decoded = parse_response(response.text)
    print("\n" + "=" * 70)
    print("RAW DECODED RESPONSE")
    print("=" * 70)
    output = json.dumps(decoded, indent=2, default=str)[:5000]
    print(output)
    if len(json.dumps(decoded, indent=2, default=str)) > 5000:
        print("\n... (truncated)")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Legacy flag handler (backward compatibility)
# ---------------------------------------------------------------------------


def _legacy_main(client: RouvyClient, args: argparse.Namespace) -> None:
    """Handle invocations using the old --endpoint / --set / --raw flags."""
    # Handle update operations
    if args.legacy_set:
        updates = _parse_settings(args.legacy_set)
        if updates is None:
            return

        print(f"Updating user settings: {updates}")
        response = client.update_user_settings(updates)
        print(f"Response: {response.status_code}")

        if response.status_code < 300:
            print("✓ Settings updated successfully")
            print("\nFetching updated settings...")
            user_response = client.get_user_settings()
            user_info = extract_user_profile(user_response.text)
            print("\n" + "=" * 70)
            print("UPDATED USER PROFILE")
            print("=" * 70)

            update_keys = set(updates.keys())

            for key, value in sorted(user_info.items()):
                formatted_key = key.replace("_", " ").title()
                is_updated = any(
                    uk in key.lower() or key.lower() in uk.lower() for uk in update_keys
                )
                marker = " \u2190 UPDATED" if is_updated else ""
                print(f"{formatted_key:25s}: {value}{marker}")
            print("=" * 70)
        return

    # Normal GET request
    endpoint = args.endpoint or "user-settings.data"
    print(f"Fetching: {endpoint}")
    response = client.get(endpoint)
    print(f"Response: {response.status_code} ({len(response.text):,} bytes)")

    decoded = parse_response(response.text)

    if args.raw:
        print("\n" + "=" * 70)
        print("RAW DECODED RESPONSE")
        print("=" * 70)
        print(json.dumps(decoded, indent=2, default=str)[:2000])
        print("\n... (truncated)")
        return

    # Format output based on endpoint
    print("\n" + "=" * 70)

    if endpoint == "user-settings.data":
        print("USER PROFILE")
        print("=" * 70)
        user_info = extract_user_profile(response.text)
        for key, value in sorted(user_info.items()):
            formatted_key = key.replace("_", " ").title()
            print(f"{formatted_key:25s}: {value}")

    elif endpoint == "user-settings/zones.data":
        print("TRAINING ZONES")
        print("=" * 70)
        if isinstance(decoded, list):
            for i in range(len(decoded)):
                if decoded[i] == "zones" and i + 1 < len(decoded):
                    zones_data = decoded[i + 1]
                    if isinstance(zones_data, dict):
                        if "power" in zones_data:
                            power = zones_data["power"]
                            print("\nPower Zones (FTP-based):")
                            if isinstance(power, dict):
                                if "values" in power:
                                    values = power["values"]
                                    if isinstance(values, list):
                                        for idx, val in enumerate(values):
                                            if idx < len(_ZONE_LABELS):
                                                print(
                                                    f"  Zone {idx + 1}"
                                                    f" ({_ZONE_LABELS[idx]:12s}): {val}% FTP"
                                                )
                                if "defaultValues" in power:
                                    print(f"  Default values: {power['defaultValues']}")

                        if "heartRate" in zones_data:
                            hr = zones_data["heartRate"]
                            print("\nHeart Rate Zones:")
                            if isinstance(hr, dict):
                                if "values" in hr:
                                    values = hr["values"]
                                    if isinstance(values, list):
                                        print(f"  Custom values: {values}")
                                if "defaultValues" in hr:
                                    default = hr["defaultValues"]
                                    if isinstance(default, list):
                                        print(f"  Default values: {default}")
                    break

    elif endpoint == "user-settings/connected-apps.data":
        print("CONNECTED APPS")
        print("=" * 70)
        if isinstance(decoded, list):
            for i in range(len(decoded)):
                if decoded[i] == "connectedApps" and i + 1 < len(decoded):
                    apps_data = decoded[i + 1]
                    if isinstance(apps_data, list):
                        print(f"\nFound {len(apps_data)} app integrations:")
                        for app in apps_data:
                            if isinstance(app, dict):
                                name = app.get("name", "Unknown")
                                connected = app.get("connected", False)
                                status = "✓ Connected" if connected else "  Not connected"
                                print(f"  {status:20s} - {name}")
                    break

    else:
        print(f"PARSED RESPONSE: {endpoint}")
        print("=" * 70)
        print(f"Type: {type(decoded).__name__}")
        if isinstance(decoded, list):
            print(f"Length: {len(decoded)} elements")
            print("\nFirst 10 elements:")
            for i in range(min(10, len(decoded))):
                print(f"  [{i}]: {repr(decoded[i])[:100]}")
        elif isinstance(decoded, dict):
            print(f"Keys: {len(decoded)} keys")
            print("\nTop-level keys:")
            for key in list(decoded.keys())[:10]:
                print(f"  - {key}: {type(decoded[key]).__name__}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()
    log_level = "DEBUG" if args.debug else args.log_level
    _configure_logging(log_level)

    email, password = load_credentials()
    config = RouvyConfig(email=email, password=password)
    client = RouvyClient(config)

    try:
        # Determine whether we're using legacy flags or subcommands
        using_legacy = args.subcommand is None and (
            args.endpoint is not None or args.legacy_set is not None or args.raw
        )

        if using_legacy:
            _legacy_main(client, args)
            return

        # Subcommand dispatch (default to 'profile' when nothing specified)
        cmd = args.subcommand or "profile"

        if cmd == "profile":
            _cmd_profile(client)
        elif cmd == "zones":
            _cmd_zones(client)
        elif cmd == "apps":
            _cmd_apps(client)
        elif cmd == "activities":
            _cmd_activities(client)
        elif cmd == "set":
            _cmd_set(client, args.settings)
        elif cmd == "raw":
            _cmd_raw(client, args.raw_endpoint)

    except ApiResponseError as e:
        print(f"API error: {e.status_code} - {e.payload}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
