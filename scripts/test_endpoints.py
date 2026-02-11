#!/usr/bin/env python3
"""Test various Rouvy API endpoints to understand their response format."""

import logging
import os
import sys
from pathlib import Path

# Add src directory to path so we can import rouvy_api_client
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from rouvy_api_client import RouvyClient, RouvyConfig

logging.basicConfig(level=logging.WARNING)

load_dotenv()
email = os.getenv("ROUVY_EMAIL")
password = os.getenv("ROUVY_PASSWORD")

config = RouvyConfig(email=email, password=password)
client = RouvyClient(config)

endpoints = [
    "user-settings.data",
    "user-settings/zones.data",
    "user-settings/connected-apps.data",
    "profile/overview.data",
    "profile.data",
    "resources/activities-pagination.data",
]

for endpoint in endpoints:
    print(f"\n{'=' * 70}")
    print(f"ENDPOINT: {endpoint}")
    print("=" * 70)
    try:
        response = client.get(endpoint)
        print(f"Status: {response.status_code}")
        print(f"Length: {len(response.text)} chars")

        # Show first 500 chars
        preview = response.text[:500]
        print(f"\nPreview:\n{preview}")

        # Save to file for analysis
        filename = f"sample_{endpoint.replace('/', '_').replace('.', '_')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"\nSaved full response to: {filename}")

    except Exception as e:
        print(f"Error: {e}")
