# Home Assistant Rouvy Integration

[![CI](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml)
[![Release](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/release.yml)
[![License](https://img.shields.io/github/license/mikejhill/home-assistant-rouvy)](LICENSE)

> **⚠️ Alpha** — This integration is under active development and is not
> yet fully tested in production. Expect breaking changes.

A custom [Home Assistant](https://www.home-assistant.io/) integration for
the [Rouvy](https://rouvy.com/) indoor cycling platform, installable via
[HACS](https://hacs.xyz/). Covers your Rouvy profile, activity history,
training zones, challenges, routes, events, career progress, and social data.

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

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `weight` | kg | `85.5` | Current body weight |
| `height` | cm | `178.0` | Current height |
| `ftp` | W | `250` | Functional Threshold Power |
| `max_heart_rate` | bpm | `185` | Maximum heart rate |
| `units` | — | `METRIC` | Preferred unit system |
| `name` | — | `John Doe` | Display name |
| `ftp_source` | — | `MANUAL` | How FTP was determined (MANUAL / ESTIMATED) |
| `country` | — | `US` | Account country code |

### Weekly Activity Stats

Current-week ride totals, refreshed each update cycle.

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `weekly_distance` | km | `142.3` | Total ride distance this week |
| `weekly_elevation` | m | `1,850` | Total elevation gain this week |
| `weekly_calories` | kcal | `3,200` | Total calories burned this week |
| `weekly_ride_time` | min | `285` | Total ride time this week |
| `weekly_ride_count` | — | `5` | Number of rides this week |
| `weekly_training_score` | — | `312` | Cumulative training score this week |

### Last Activity

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `last_activity_title` | — | `Col du Galibier` | Title of the most recent ride |
| `last_activity_distance` | km | `34.2` | Distance of the most recent ride |
| `last_activity_duration` | min | `62` | Duration of the most recent ride |
| `last_activity_date` | timestamp | `2026-04-10T07:30:00Z` | Start time of the most recent ride |
| `total_activities` | — | `247` | Total number of recent activities |

### Challenges

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `active_challenges` | — | `3` | Number of currently active challenges |
| `completed_challenges` | — | `12` | Number of completed challenges |

### Training Zones

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `power_zones` | — | `[55, 75, 90, 105, 120, 150]` | Power zone boundaries (% of FTP) |
| `hr_zones` | — | `[60, 65, 75, 82, 89, 94]` | Heart rate zone boundaries (% of max HR) |

### Connected Apps

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `connected_apps_count` | — | `3` | Total connected third-party apps |
| `connected_apps_active` | — | `2` | Number of actively connected apps |

### Routes

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `favorite_routes_count` | — | `15` | Number of favorited routes |
| `routes_online_riders` | — | `42` | Total online riders across favorites |

### Events

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `upcoming_events_count` | — | `2` | Number of upcoming events |
| `next_event` | — | `Saturday Morning Race` | Title of the next scheduled event |
| `next_event_time` | — | `2026-04-12T08:00:00Z` | Start time of the next scheduled event |

### Career

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `career_level` | — | `25` | Current career level |
| `total_xp` | — | `9,500` | Total experience points |
| `total_coins` | — | `3,200` | Total coins earned |
| `career_total_distance` | km | `4,567.8` | Lifetime total distance ridden |
| `career_total_elevation` | m | `45,678` | Lifetime total elevation gained |
| `career_total_time` | h | `312.5` | Lifetime total ride time |
| `career_total_activities` | — | `247` | Lifetime total activity count |
| `career_achievements` | — | `37` | Total achievements unlocked |
| `career_trophies` | — | `12` | Total trophies earned |

### Social

| Sensor | Unit | Example | Description |
| --- | --- | --- | --- |
| `friends_count` | — | `42` | Total number of friends |
| `friends_online` | — | `5` | Number of friends currently online |

## Services

### Update Services

| Service | Parameters | Description |
| --- | --- | --- |
| `rouvy.update_weight` | `weight` (kg) | Update body weight |
| `rouvy.update_height` | `height` (cm) | Update height |
| `rouvy.update_units` | `units` (METRIC/IMPERIAL) | Switch unit system |
| `rouvy.update_profile` | `userName`, `firstName`, `lastName`, `team`, `countryIsoCode`, `accountPrivacy` | Update profile fields |
| `rouvy.update_timezone` | `timezone` (IANA) | Update timezone |
| `rouvy.update_ftp` | `ftp_source` (MANUAL/ESTIMATED), `value` (W) | Update FTP source and value |
| `rouvy.update_zones` | `zone_type` (power/heartRate), `zones` (list) | Update zone boundaries |
| `rouvy.update_max_heart_rate` | `max_heart_rate` (bpm) | Update maximum heart rate |
| `rouvy.update_settings` | `settings` (object) | Update arbitrary settings |

### Action Services

| Service | Parameters | Description |
| --- | --- | --- |
| `rouvy.register_challenge` | `slug` | Register for a challenge |
| `rouvy.register_event` | `event_id` (UUID) | Register for an event |
| `rouvy.unregister_event` | `event_id` (UUID) | Unregister from an event |

### Query Services

These services return data and can be used in automations via
`response_variable`.

| Service | Returns | Description |
| --- | --- | --- |
| `rouvy.get_profile` | `{profile: {...}}` | Full user profile |
| `rouvy.get_events` | `{events: [...]}` | Upcoming events |
| `rouvy.get_challenges` | `{challenges: [...]}` | Available challenges |
| `rouvy.get_routes` | `{routes: [...]}` | Favorite routes |
| `rouvy.get_activities` | `{activities: [...]}` | Recent activities |
| `rouvy.get_career` | `{career: {...}}` | Career progression stats |

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

All commands support a `--json` flag for machine-readable output.

**Read commands:**

```bash
uv run rouvy-api profile          # User profile (default)
uv run rouvy-api zones            # Training zones (FTP, HR)
uv run rouvy-api activities       # Recent activities
uv run rouvy-api activity-stats --year 2026 --month 1  # Weekly stats
uv run rouvy-api apps             # Connected apps
uv run rouvy-api career           # Career progression
uv run rouvy-api challenges       # Available challenges
uv run rouvy-api events           # Upcoming events
uv run rouvy-api friends          # Friends summary
uv run rouvy-api routes           # Favorite routes
uv run rouvy-api raw <endpoint>   # Raw decoded turbo-stream response
```

**Write commands:**

```bash
uv run rouvy-api set-weight 86.5
uv run rouvy-api set-height 178
uv run rouvy-api set-ftp 250 --source MANUAL
uv run rouvy-api set-max-hr 185
uv run rouvy-api set-units METRIC           # METRIC or IMPERIAL
uv run rouvy-api set-timezone "Europe/Prague"
uv run rouvy-api set-profile --username "NewName" --first-name "John"
uv run rouvy-api set-zones --type power --boundaries 55,75,90,105,120,150
uv run rouvy-api register-challenge <id>
uv run rouvy-api register-event <id>
uv run rouvy-api unregister-event <id>
```

**JSON output:**

```bash
uv run rouvy-api profile --json | jq .weight
uv run rouvy-api zones --json
```

## Development

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

### Getting Started

```bash
uv sync              # Install all dependencies
uv run pytest -q     # Run tests (483 unit tests)
uv run ruff check .  # Lint
uv run ruff format . # Format
```

### Integration Tests

> **⚠️ Warning:** Integration tests run against the **real** Rouvy API and
> **will modify** account settings (weight, height, timezone, FTP, zones,
> username, etc.). Settings are restored on a best-effort basis, but
> restoration may fail if tests are interrupted.

**Local:**

```bash
export ROUVY_TEST_EMAIL="email@example.com"
export ROUVY_TEST_PASSWORD="password"
uv run pytest tests/integration/ -m integration -v
```

**GitHub Actions:** Trigger the **Integration Tests** workflow manually from
the Actions tab. Configure the following secrets in a `rouvy-test`
environment:

- `ROUVY_TEST_EMAIL` — Rouvy account email
- `ROUVY_TEST_PASSWORD` — Rouvy account password

### Project Structure

```text
custom_components/rouvy/     # HA integration (HACS root)
├── api_client/              # Embedded API client
│   ├── models.py            # Typed frozen dataclasses
│   ├── parser.py            # Turbo-stream response decoder
│   └── ...
├── coordinator.py           # DataUpdateCoordinator
├── sensor.py                # 41 sensor descriptions
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
