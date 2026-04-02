#!/usr/bin/env python3
"""Debug script to understand turbo-stream structure."""

import json
import os
import sys
from pathlib import Path

# Add src directory to path so we can import rouvy_api_client
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from rouvy_api_client import RouvyClient, RouvyConfig, TurboStreamDecoder

load_dotenv()
email = os.getenv("ROUVY_EMAIL")
password = os.getenv("ROUVY_PASSWORD")

config = RouvyConfig(email=email, password=password)
client = RouvyClient(config)

response = client.get("user-settings.data")

# Parse the first line only
lines = response.text.strip().split("\n")
raw_data = json.loads(lines[0])

print("RAW DATA STRUCTURE:")
print("=" * 70)

# Find email-related section
for i in range(len(raw_data)):
    if raw_data[i] == "email":
        print(f"\nContext around 'email' (index {i}):")
        start = max(0, i - 5)
        end = min(len(raw_data), i + 10)
        for j in range(start, end):
            marker = " <-- HERE" if j == i else ""
            print(f"  [{j}]: {repr(raw_data[j])}{marker}")
        break

# Find userProfile section
for i in range(len(raw_data)):
    if raw_data[i] == "userProfile":
        print(f"\nContext around 'userProfile' (index {i}):")
        start = max(0, i - 2)
        end = min(len(raw_data), i + 5)
        for j in range(start, end):
            marker = " <-- HERE" if j == i else ""
            print(f"  [{j}]: {repr(raw_data[j])}{marker}")

        # The value should be an object
        if i + 1 < len(raw_data):
            profile_obj = raw_data[i + 1]
            print(f"\nuserProfile object: {json.dumps(profile_obj, indent=2)}")
        break

print("\n" + "=" * 70)
print("DECODED STRUCTURE:")
print("=" * 70)

decoder = TurboStreamDecoder()
decoded = decoder.decode(response.text)

# Show just the first 20 elements decoded
if isinstance(decoded, list):
    for i in range(min(20, len(decoded))):
        print(f"[{i}]: {repr(decoded[i])}")
