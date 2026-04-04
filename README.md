# Home Assistant Rouvy Integration

[![CI](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml)
[![Release](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **⚠️ Alpha** — This project is under active development. The Home
> Assistant integration and CLI are functional but not yet fully tested
> in production. Expect breaking changes.

A native [Home Assistant](https://www.home-assistant.io/) integration for the [Rouvy](https://rouvy.com/) indoor cycling platform, installable via [HACS](https://hacs.xyz/). Includes an embedded API client library and a standalone CLI tool.

## Features

- **Typed Data Models**: Frozen dataclasses for user profiles, training zones, connected apps, and activities
- **CLI with Subcommands**: `profile`, `zones`, `apps`, `activities`, `set`, and `raw` commands
- **Automatic Authentication**: Session-based login with automatic re-auth on 401
- **Turbo-Stream Parser**: Full decoder for the Remix turbo-stream response format
- **Home Assistant Integration**: Native config-flow integration with sensors and write services
- **Reauth Support**: Automatic re-authentication flow when credentials expire
- **HACS Compatible**: Installable directly from HACS as a custom repository
- **Structured Logging**: Debug and info-level logging with extra context

## Installation

```bash
# Development (install with dev dependencies)
uv sync

# Production only
uv sync --no-dev
```

## Home Assistant Integration

A native Home Assistant custom integration is provided in `custom_components/rouvy/`. It is installable via [HACS](https://hacs.xyz/) as a custom repository.

### Features

- **Config Flow**: Add via the HA UI with email/password credentials
- **Sensors**: Weight, height, FTP, max heart rate, units, display name
- **Services**: `rouvy.update_weight`, `rouvy.update_height`, `rouvy.update_settings`
- **Polling**: Automatic hourly data refresh via DataUpdateCoordinator

### HACS Installation

1. In HACS, go to **Integrations** → **⋮** → **Custom repositories**
2. Add this repository URL with category **Integration**
3. Install the **Rouvy** integration
4. Restart Home Assistant
5. Go to **Settings** → **Devices & Services** → **Add Integration** → search for **Rouvy**

## Setup

Create a `.env` file in the project root with your Rouvy credentials:

```bash
cp .env.example .env
```

Then edit `.env` with your credentials:

```ini
ROUVY_EMAIL=your-email@example.com
ROUVY_PASSWORD=your-password
```

## Configuration

The `RouvyConfig` dataclass accepts:

- `email`: Login email address (**required**)
- `password`: Login password (**required**)
- `timeout_seconds`: Request timeout in seconds (default: 30.0)

Note: `base_url` and `auth_url` are hardcoded to `https://riders.rouvy.com` as these are fixed for the Rouvy platform.

## Usage

### Command-Line Interface

```bash
# Using uv (recommended)
uv run rouvy-api <command>

# Using the package module
python -m custom_components.rouvy.api_client <command>

# Using the console script (after install)
rouvy-api <command>
```

#### Subcommands

```bash
# View user profile
rouvy-api profile

# View training zones
rouvy-api zones

# View connected apps
rouvy-api apps

# View recent activities
rouvy-api activities

# Update settings
rouvy-api set weight=86 height=178

# Raw decoded response from any endpoint
rouvy-api raw user-settings/zones.data
```

#### Legacy Flags (backward compatible)

```bash
rouvy-api --endpoint user-settings.data
rouvy-api --set weight=86
rouvy-api --raw
rouvy-api --debug
```

### Scripts

The `scripts/` directory contains additional utility and demo scripts:

- `demo_parser.py` - Comprehensive parser demo across multiple endpoints
- `test_endpoints.py` - Test different Rouvy API endpoints
- `debug_parser.py` - Debug utility for analyzing response structure

Run scripts with:

```bash
uv run python scripts/demo_parser.py
```

### Programmatic Usage

```python
from custom_components.rouvy.api_client import RouvyClient, RouvyConfig

# Initialize client
client = RouvyClient(
    RouvyConfig(
        email="you@example.com",
        password="your-password",
    )
)

# Typed model access
profile = client.get_user_profile()
print(f"{profile.first_name} {profile.last_name}: {profile.weight_kg} kg")

zones = client.get_training_zones()
print(f"FTP: {zones.ftp_watts}W, Max HR: {zones.max_heart_rate} bpm")

apps = client.get_connected_apps()
for app in apps:
    print(f"{app.name}: {'connected' if app.connected else 'not connected'}")

summary = client.get_activity_summary()
print(f"{summary.total_count} activities, {summary.total_distance_km:.1f} km total")

# Update settings
client.update_user_settings({"weight": 86, "height": 178})

# Low-level access
response = client.get("user-settings.data")
decoded = parse_response(response.text)
```

## Turbo-Stream Response Format

Rouvy API responses use the [turbo-stream format](https://github.com/jacob-ebey/turbo-stream) from Remix framework. This format supports more data types than JSON (Dates, Promises, undefined/null) and uses indexed references to deduplicate repeated values.

### Format Characteristics

1. **Indexed References**: Objects use `{"_N": value}` where `N` is the array index of the key name
2. **Special Types**:
   - Dates: `["D", timestamp_ms]` → parsed to `datetime` object
   - Promises: `["P", id]` → resolved from subsequent response lines
   - Sentinels: `-5` (undefined), `-7` (null)
3. **Multi-line Responses**: First line contains main JSON array, subsequent lines contain promise resolutions

### Using the Parser

The `custom_components.rouvy.api_client` module provides a generic turbo-stream parser:

```python
from custom_components.rouvy.api_client import parse_response, extract_user_profile

# Generic parsing of any endpoint
response = client.get("user-settings/zones.data")
decoded = parse_response(response.text)

# Specialized extractor for user profile
response = client.get("user-settings.data")
user_profile = extract_user_profile(response.text)
print(user_profile)
# {
#   'email': 'user@example.com',
#   'username': 'username',
#   'ftp_watts': 250,
#   'weight_kg': 75,
#   'country': 'US',
#   ...
# }
```

See `scripts/demo_parser.py` for comprehensive examples of parsing different endpoints.

### Tested Endpoints

- `user-settings.data` - User profile and preferences
- `user-settings/zones.data` - Power and heart rate training zones
- `user-settings/connected-apps.data` - Connected third-party apps
- `profile/overview.data` - Profile overview with recent activities (large response)
- `resources/activities-pagination.data` - Paginated activity list

## Documentation

Comprehensive documentation and reference materials are in the `docs/` directory:

- [**docs/architecture/turbo-stream.md**](docs/architecture/turbo-stream.md) - Detailed explanation of the turbo-stream format discovery and implementation
- [**docs/private-samples/**](docs/private-samples/) - Sample API responses for reference (git-ignored, local only)

## Logging

The client uses Python's standard `logging` module. Enable logging by configuring
the `custom_components.rouvy.api_client` logger or the `custom_components.rouvy.api_client.client` module logger.

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
```

Security note: request/response bodies and credentials are not logged by
default to avoid leaking sensitive data.

Structured log context is attached to log records via `extra`. Example output
with a JSON formatter might look like:

```json
{"level":"DEBUG","name":"custom_components.rouvy.api_client.client","message":"HTTP request completed","method":"GET","url":"https://riders.rouvy.com/user-settings.data","status_code":200,"duration_ms":12.34}
```

## Testing

```bash
uv run pytest -q
```
