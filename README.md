# Home Assistant Rouvy Integration

[![CI](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/ci.yml)
[![Rouvy contract](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/contract.yml/badge.svg)](https://github.com/mikejhill/home-assistant-rouvy/actions/workflows/contract.yml)
[![License](https://img.shields.io/github/license/mikejhill/home-assistant-rouvy)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) integration for the
[Rouvy](https://rouvy.com/) indoor cycling platform, installable with
[HACS](https://hacs.xyz/). It turns your Rouvy account into sensors (profile,
weekly, monthly and yearly totals, last ride, challenges, events, routes,
career, friends) and actions you can call from automations. A standalone
async Python library and the `rouvy-api` CLI are included.

Rouvy has no public API. This project uses the same data routes as the
riders.rouvy.com website, politely (hourly) and with a user agent that
identifies the project. See the [project charter](docs/project-charter.md).

## Requirements

- Home Assistant 2026.10 or newer.
- A Rouvy account with a password. If you only sign in with Google, Apple, or
  Facebook, set a password under **Security** on account.rouvy.com first.

## Installation (HACS)

1. In HACS, open **⋮ → Custom repositories** and add
   `https://github.com/mikejhill/home-assistant-rouvy` as an **Integration**.
2. Install **Rouvy** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Rouvy** and sign
   in with your Rouvy email and password.

If Rouvy later rejects the saved password, Home Assistant asks you to sign in
again. To change the stored password yourself, use **Reconfigure** on the
integration.

## Sensors

| Group | Sensors |
| --- | --- |
| Profile | Weight, Height, FTP (manual value, else Rouvy's estimate), Max heart rate, FTP source*, Units*, Name*, Country* (disabled by default) |
| Current week (all activity types) | Weekly distance, elevation, calories, ride time, activities, training score |
| Month / year to date | Monthly distance and ride time; yearly distance, elevation, and ride time |
| Last activity | Last activity (title), distance, duration, date |
| Challenges and events | Active challenges, Completed challenges, Upcoming events and Next event / Next event time (events you have joined) |
| Routes | Favorite routes (your favourites collection), Online riders on favorite routes |
| Career and social | Career level, Total XP, Achievements, Trophies, Friends, Online friends |
| Configuration* | Power zones, Heart rate zones, Connected apps, Active connected apps |

\* Diagnostic entities. Data refreshes every hour. If one section (for example
events) cannot be fetched, only its sensors are affected: they keep their last
value, or become unavailable if there is none.

## Actions

| Action | Fields |
| --- | --- |
| `rouvy.update_weight` | `weight` (kg) |
| `rouvy.update_height` | `height` (cm) |
| `rouvy.update_units` | `units` (`METRIC` / `IMPERIAL`) |
| `rouvy.update_settings` | `settings`: any of `weight`, `height`, `units` |
| `rouvy.update_profile` | `username`, `first_name`, `last_name`, `country`, `gender`, `date_of_birth`, `account_privacy` |
| `rouvy.update_timezone` | `timezone` (IANA name) |
| `rouvy.update_ftp` | `ftp_source` (`MANUAL` / `ESTIMATED`), `value` (W) |
| `rouvy.update_zones` | `zone_type` (`power` / `heartRate`), `zones` (increasing %) |
| `rouvy.update_max_heart_rate` | `max_heart_rate` (bpm) |
| `rouvy.register_challenge` | `slug` |
| `rouvy.register_event` / `rouvy.unregister_event` | `event_id` |

Query actions return data for use with `response_variable`:
`rouvy.get_profile`, `rouvy.get_events`, `rouvy.get_challenges`,
`rouvy.get_routes`, `rouvy.get_activities`, `rouvy.get_career`.

```yaml
action: rouvy.get_events
response_variable: rouvy
```

## Troubleshooting

| Message | Meaning |
| --- | --- |
| Rouvy did not accept this email and password | Wrong credentials, or a social-sign-in-only account without a password |
| Rouvy is temporarily blocking sign-in attempts | Too many attempts; wait a few minutes |
| Rouvy's firewall rejected the request / did not start a session | Rouvy changed its site; check for an update (the daily canary usually catches this first) |

Debug logging:

```yaml
logger:
  logs:
    custom_components.rouvy: debug
```

Passwords and response bodies are never logged. **Download diagnostics** on the
integration page produces a redacted report for issues.

## CLI

```bash
uv tool install git+https://github.com/mikejhill/home-assistant-rouvy
```

Set `ROUVY_EMAIL` and `ROUVY_PASSWORD` (environment or a `.env` file), then:

```bash
rouvy-api login-check
```

```bash
rouvy-api events --json
```

Run `rouvy-api --help` for every command (reads, writes, and `raw <route>.data`).

## Development

Python 3.14 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync
```

```bash
uv run poe check
```

`poe check` runs formatting, linting (including security rules and a
cyclomatic complexity limit), strict type checking, the vendoring check, the
full test suite with ≥95% branch coverage, and performance budgets. Other
tasks: `poe fix`, `poe vendor`, `poe contract` (live canary, no account),
`poe live` (read-only, needs `ROUVY_TEST_EMAIL` / `ROUVY_TEST_PASSWORD`).

Read [architecture](docs/architecture.md), [testing](docs/testing.md),
[releasing](docs/releasing.md), and the [decision records](docs/adr/) before
larger changes. Enable the pre-commit hook with
`git config core.hooksPath .githooks`. The library in
`src/rouvy_api` is the source of truth; `custom_components/rouvy/rouvy_api` is
generated by `poe vendor`.

## License

[MIT](LICENSE)
