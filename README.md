# Home Assistant Rouvy Integration

[![CI](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml)
[![Release](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **⚠️ Alpha** — This integration is under active development and is not
> yet fully tested in production. Expect breaking changes.

A custom [Home Assistant](https://www.home-assistant.io/) integration for
the [Rouvy](https://rouvy.com/) indoor cycling platform, installable via
[HACS](https://hacs.xyz/). Exposes 33 sensors and 3 services covering your
Rouvy profile, activity history, training zones, challenges, routes, events,
career progress, and social data.

## Installation (HACS)

1. In HACS, go to **Integrations** → **⋮** → **Custom repositories**.
2. Add `https://github.com/mikejhill/home-assistant-rouvy` with category
   **Integration**.
3. Install the **Rouvy** integration and restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration** →
   search for **Rouvy**.
5. Enter your Rouvy email and password.

Data is refreshed automatically every hour. Credentials are stored in the
Home Assistant config entry and sessions are re-authenticated transparently
on expiry.

## Sensors

All sensors are created under the `sensor.rouvy_*` entity namespace.

### Profile

| Sensor | Unit | Description |
| --- | --- | --- |
| `weight` | kg | Current body weight |
| `height` | cm | Current height |
| `ftp` | W | Functional Threshold Power |
| `max_heart_rate` | bpm | Maximum heart rate |
| `units` | — | Preferred unit system (METRIC / IMPERIAL) |
| `name` | — | Display name |

### Weekly Activity Stats

Current-week ride totals, refreshed each update cycle.

| Sensor | Unit | Description |
| --- | --- | --- |
| `weekly_distance` | km | Total ride distance this week |
| `weekly_elevation` | m | Total elevation gain this week |
| `weekly_calories` | kcal | Total calories burned this week |
| `weekly_ride_time` | min | Total ride time this week |
| `weekly_ride_count` | — | Number of rides this week |
| `weekly_training_score` | — | Cumulative training score this week |

### Last Activity

| Sensor | Unit | Description |
| --- | --- | --- |
| `last_activity_title` | — | Title of the most recent ride |
| `last_activity_distance` | km | Distance of the most recent ride |
| `last_activity_duration` | min | Duration of the most recent ride |
| `last_activity_date` | timestamp | Start time of the most recent ride |
| `total_activities` | — | Total number of recent activities |

### Challenges

| Sensor | Unit | Description |
| --- | --- | --- |
| `active_challenges` | — | Number of currently active challenges |
| `completed_challenges` | — | Number of completed challenges |

### Training Zones

| Sensor | Unit | Description |
| --- | --- | --- |
| `power_zones` | — | Power zone boundaries (% of FTP) |
| `hr_zones` | — | Heart rate zone boundaries (% of max HR) |

### Connected Apps

| Sensor | Unit | Description |
| --- | --- | --- |
| `connected_apps_count` | — | Total connected third-party apps |
| `connected_apps_active` | — | Number of actively connected apps |

### Routes

| Sensor | Unit | Description |
| --- | --- | --- |
| `favorite_routes_count` | — | Number of favorited routes |
| `routes_online_riders` | — | Total online riders across favorites |

### Events

| Sensor | Unit | Description |
| --- | --- | --- |
| `upcoming_events_count` | — | Number of upcoming events |
| `next_event` | — | Title of the next scheduled event |

### Career

| Sensor | Unit | Description |
| --- | --- | --- |
| `career_level` | — | Current career level |
| `total_xp` | — | Total experience points |
| `total_coins` | — | Total coins earned |
| `career_total_distance` | km | Lifetime total distance ridden |

### Social

| Sensor | Unit | Description |
| --- | --- | --- |
| `friends_count` | — | Total number of friends |
| `friends_online` | — | Number of friends currently online |

## Services

| Service | Description |
| --- | --- |
| `rouvy.update_weight` | Update body weight (kg) in Rouvy |
| `rouvy.update_height` | Update height (cm) in Rouvy |
| `rouvy.update_settings` | Update arbitrary profile settings (key-value pairs) |

## Logging

Add the following to your Home Assistant `configuration.yaml` to enable
debug logging for this integration:

```yaml
logger:
  logs:
    custom_components.rouvy: debug
```

Credentials and response bodies are never logged.

## CLI Tool

A standalone CLI is included for direct interaction with the Rouvy API
outside of Home Assistant.

### Setup

Create a `.env` file in the project root:

```ini
ROUVY_EMAIL=your-email@example.com
ROUVY_PASSWORD=your-password
```

### Commands

```bash
uv run rouvy-api profile       # View user profile
uv run rouvy-api zones         # View training zones
uv run rouvy-api apps          # View connected apps
uv run rouvy-api activities    # View recent activities
uv run rouvy-api set weight=86 height=178  # Update settings
uv run rouvy-api raw user-settings/zones.data  # Raw decoded response
```

## Development

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

### Getting Started

```bash
uv sync              # Install all dependencies
uv run pytest -q     # Run tests (438 tests)
uv run ruff check .  # Lint
uv run ruff format . # Format
```

### Project Structure

```text
custom_components/rouvy/     # HA integration (HACS root)
├── api_client/              # Embedded API client
│   ├── models.py            # Typed frozen dataclasses
│   ├── parser.py            # Turbo-stream response decoder
│   └── ...
├── coordinator.py           # DataUpdateCoordinator
├── sensor.py                # 33 sensor descriptions
├── config_flow.py           # HA config flow + reauth
├── services.yaml            # Service definitions
└── manifest.json            # HA integration manifest
tests/                       # pytest test suite
scripts/                     # Development utility scripts
docs/architecture/           # Technical documentation
```

### Architecture Notes

Rouvy uses a [turbo-stream](https://github.com/jacob-ebey/turbo-stream)
response format (from Remix) rather than a conventional REST API. The
embedded `api_client` includes a full turbo-stream decoder that handles
indexed references, special types (Dates, Promises, sentinels), and
multi-line promise resolution.

## Contributing

1. Fork the repository and create a feature branch.
2. Ensure `uv run pytest -q` passes with no failures.
3. Ensure `uv run ruff check . && uv run ruff format --check .` is clean.
4. Open a pull request.

## License

[MIT](LICENSE)
