#!/usr/bin/env python3
"""
Rouvy API client - Command-line interface for making API calls.
"""

import argparse
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

from rouvy_api_client import (
    ApiResponseError,
    RouvyClient,
    RouvyConfig,
    extract_user_profile,
    parse_response,
)


LOGGER = logging.getLogger(__name__)


def load_credentials() -> tuple[str, str]:
    """Load email and password from .env file."""
    load_dotenv()
    email: Optional[str] = os.getenv("ROUVY_EMAIL")
    password: Optional[str] = os.getenv("ROUVY_PASSWORD")

    if not email or not password:
        raise ValueError("ROUVY_EMAIL and ROUVY_PASSWORD must be set in .env file")

    return email, password


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rouvy API client - Fetch and parse API endpoints"
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        default="user-settings.data",
        help="API endpoint to call (default: user-settings.data)",
    )
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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw decoded response instead of formatted output",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Update a user setting (can be used multiple times). Supported fields: weight, height, units (METRIC/IMPERIAL). Example: --set weight=86 --set height=178",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    log_level = "DEBUG" if args.debug else args.log_level
    _configure_logging(log_level)

    email, password = load_credentials()

    config = RouvyConfig(
        email=email,
        password=password,
    )

    client = RouvyClient(config)

    try:
        # Handle update operations
        if args.set:
            updates = {}
            for setting in args.set:
                if "=" not in setting:
                    print(f"Error: Invalid format '{setting}'. Use KEY=VALUE format.")
                    return
                key, value = setting.split("=", 1)
                # Try to convert to appropriate type
                try:
                    # Try int first
                    updates[key] = int(value)
                except ValueError:
                    try:
                        # Try float
                        updates[key] = float(value)
                    except ValueError:
                        # Keep as string
                        updates[key] = value

            print(f"Updating user settings: {updates}")
            response = client.update_user_settings(updates)
            print(f"Response: {response.status_code}")

            if response.status_code < 300:
                print("✓ Settings updated successfully")
                # Fetch and show updated settings
                print("\nFetching updated settings...")
                user_response = client.get_user_settings()
                user_info = extract_user_profile(user_response.text)
                print("\n" + "=" * 70)
                print("UPDATED USER PROFILE")
                print("=" * 70)

                # Create a mapping for common field name variations
                update_keys = set(updates.keys())

                for key, value in sorted(user_info.items()):
                    formatted_key = key.replace("_", " ").title()
                    # Check if this field was updated (handle variations like weight/weight_kg)
                    is_updated = any(
                        uk in key.lower() or key.lower() in uk.lower()
                        for uk in update_keys
                    )
                    marker = " \u2190 UPDATED" if is_updated else ""
                    print(f"{formatted_key:25s}: {value}{marker}")
                print("=" * 70)
            return

        # Normal GET request
        print(f"Fetching: {args.endpoint}")
        response = client.get(args.endpoint)
        print(f"Response: {response.status_code} ({len(response.text):,} bytes)")

        # Parse the response using generic turbo-stream decoder
        decoded = parse_response(response.text)

        if args.raw:
            # Show raw decoded structure
            print("\n" + "=" * 70)
            print("RAW DECODED RESPONSE")
            print("=" * 70)
            print(json.dumps(decoded, indent=2, default=str)[:2000])
            print("\n... (truncated)")
            return

        # Format output based on endpoint
        print("\n" + "=" * 70)

        if args.endpoint == "user-settings.data":
            print("USER PROFILE")
            print("=" * 70)
            user_info = extract_user_profile(response.text)
            for key, value in sorted(user_info.items()):
                formatted_key = key.replace("_", " ").title()
                print(f"{formatted_key:25s}: {value}")

        elif args.endpoint == "user-settings/zones.data":
            print("TRAINING ZONES")
            print("=" * 70)
            # Find zones in decoded structure
            if isinstance(decoded, list):
                for i in range(len(decoded)):
                    if decoded[i] == "zones" and i + 1 < len(decoded):
                        zones_data = decoded[i + 1]
                        if isinstance(zones_data, dict):
                            # Power zones
                            if "power" in zones_data:
                                power = zones_data["power"]
                                print("\nPower Zones (FTP-based):")
                                if isinstance(power, dict):
                                    if "values" in power:
                                        values = power["values"]
                                        if isinstance(values, list):
                                            zone_names = [
                                                "Recovery",
                                                "Endurance",
                                                "Tempo",
                                                "Threshold",
                                                "VO2Max",
                                                "Anaerobic",
                                            ]
                                            for idx, val in enumerate(values):
                                                if idx < len(zone_names):
                                                    print(
                                                        f"  Zone {idx+1} ({zone_names[idx]:12s}): {val}% FTP"
                                                    )
                                    if "defaultValues" in power:
                                        print(
                                            f"  Default values: {power['defaultValues']}"
                                        )

                            # Heart rate zones
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

        elif args.endpoint == "user-settings/connected-apps.data":
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
                                    status = (
                                        "✓ Connected"
                                        if connected
                                        else "  Not connected"
                                    )
                                    print(f"  {status:20s} - {name}")
                        break

        else:
            # Generic output for unknown endpoints
            print(f"PARSED RESPONSE: {args.endpoint}")
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

    except ApiResponseError as e:
        print(f"API error: {e.status_code} - {e.payload}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
