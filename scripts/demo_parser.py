#!/usr/bin/env python3
"""
Comprehensive example demonstrating the generic turbo-stream parser
with multiple Rouvy API endpoints.
"""

import logging
import os
import sys
from pathlib import Path

# Add src directory to path so we can import rouvy_api_client
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from rouvy_api_client import (
    RouvyClient,
    RouvyConfig,
    extract_user_profile,
    parse_response,
)

logging.basicConfig(level=logging.WARNING)

load_dotenv()
email = os.getenv("ROUVY_EMAIL")
password = os.getenv("ROUVY_PASSWORD")

config = RouvyConfig(email=email, password=password)
client = RouvyClient(config)

print("=" * 70)
print("ROUVY API TURBO-STREAM PARSER DEMO")
print("=" * 70)
print("\nRouvy uses the turbo-stream format from Remix framework")
print("(https://github.com/jacob-ebey/turbo-stream)")
print("\nKey features:")
print("- Indexed references to deduplicate repeated values")
print("- Special types: Dates, Promises, undefined/null sentinels")
print("- Multi-line responses with promise resolutions")
print()

# Example 1: User Settings with specialized extractor
print("\n" + "=" * 70)
print("EXAMPLE 1: User Settings (with specialized extractor)")
print("=" * 70)

response = client.get("user-settings.data")
user_profile = extract_user_profile(response.text)

print("\nExtracted Profile:")
for key, value in sorted(user_profile.items()):
    print(f"  {key:20s}: {value}")

# Example 2: Generic parsing of any endpoint
print("\n" + "=" * 70)
print("EXAMPLE 2: User Settings Zones (generic parser)")
print("=" * 70)

try:
    response = client.get("user-settings/zones.data")
    decoded = parse_response(response.text)

    # Navigate the decoded structure
    if isinstance(decoded, list) and len(decoded) > 0:
        # Find zones data
        for i in range(len(decoded)):
            if decoded[i] == "zones" and i + 1 < len(decoded):
                zones_data = decoded[i + 1]
                if isinstance(zones_data, dict):
                    print("\nPower Zones:")
                    if "power" in zones_data:
                        power = zones_data["power"]
                        if isinstance(power, dict) and "values" in power:
                            print(f"  {power['values']}")

                    print("\nHeart Rate Zones:")
                    if "heartRate" in zones_data:
                        hr = zones_data["heartRate"]
                        if isinstance(hr, dict) and "values" in hr:
                            print(f"  {hr['values']}")
                break
except Exception as e:
    print(f"Could not fetch zones: {e}")

# Example 3: Connected Apps
print("\n" + "=" * 70)
print("EXAMPLE 3: Connected Apps (generic parser)")
print("=" * 70)

try:
    response = client.get("user-settings/connected-apps.data")
    decoded = parse_response(response.text)

    # Find connected apps data
    for i in range(len(decoded) if isinstance(decoded, list) else 0):
        if decoded[i] == "connectedApps" and i + 1 < len(decoded):
            apps_data = decoded[i + 1]
            if isinstance(apps_data, list):
                print(f"\nFound {len(apps_data)} connected app entries")
                for app in apps_data[:3]:  # Show first 3
                    if isinstance(app, dict):
                        print(f"  - {app.get('name', 'Unknown')}: {app.get('connected', False)}")
            break
except Exception as e:
    print(f"Could not fetch connected apps: {e}")

# Example 4: Profile Overview
print("\n" + "=" * 70)
print("EXAMPLE 4: Profile Overview (large response)")
print("=" * 70)

try:
    response = client.get("profile/overview.data")
    print(f"\nResponse size: {len(response.text):,} characters")
    decoded = parse_response(response.text)
    print(
        f"Decoded to: {type(decoded).__name__} with {len(decoded) if isinstance(decoded, list) else '?'} elements"
    )

    # Find activity data
    for i in range(len(decoded) if isinstance(decoded, list) else 0):
        if decoded[i] == "activities" and i + 1 < len(decoded):
            activities = decoded[i + 1]
            if isinstance(activities, list):
                print(f"\nFound {len(activities)} recent activities")
                for activity in activities[:3]:  # Show first 3
                    if isinstance(activity, dict):
                        name = activity.get("name", "Unknown")
                        distance = activity.get("distance", 0)
                        print(f"  - {name}: {distance / 1000:.1f} km")
            break
except Exception as e:
    print(f"Could not fetch profile overview: {e}")

print("\n" + "=" * 70)
print("PARSER DOCUMENTATION")
print("=" * 70)
print(
    """
The TurboStreamDecoder handles these format features:

1. Indexed References:
   - Objects use {"_N": value} where N is the array index of the key
   - Values can also be indices pointing to other array elements

2. Special Types:
   - Dates: ["D", timestamp_ms] → datetime object
   - Promises: ["P", id] → resolved from subsequent lines
   - Sentinels: -5 (undefined), -7 (null)

3. Multi-line Responses:
   - Line 1: Main JSON array with encoded data
   - Line 2+: Promise resolutions (e.g., "P132:[...]")

4. Resolution Rules:
   - Integer values in indexed keys (_N) are resolved as indices
   - Integer values elsewhere are treated as literals
   - Recursive resolution with cycle detection

For implementation details, see: rouvy_api_client/parser.py
"""
)

print("\n" + "=" * 70)
