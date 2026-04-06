# Home Assistant Rouvy

A [Home Assistant](https://www.home-assistant.io/) custom integration for the
[Rouvy](https://rouvy.com/) indoor cycling platform, installable via
[HACS](https://hacs.xyz/).

## Features

- **41 sensors** — profile, training zones, career stats, activities, events,
  challenges, routes, friends, and connected apps
- **18 services** — update weight, height, FTP, max heart rate, zones, profile
  fields, timezone, units, privacy, and manage event/challenge registrations
- **CLI tool** — standalone command-line interface with 23 subcommands and
  `--json` output
- **HACS-compatible** — install directly from the HACS custom repositories UI

## Quick Start

### Home Assistant Integration

1. Install via HACS → Custom Repositories → add
   `mikejhill/home-assistant-rouvy`
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Rouvy**
4. Enter your Rouvy credentials

### CLI Tool

```bash
pip install home-assistant-rouvy  # or: uv tool install .
rouvy-api profile
rouvy-api zones --json
```

See the [Getting Started](getting-started.md) guide for full setup instructions.

## How It Works

The integration uses an embedded API client that communicates with Rouvy's
web application endpoints. Rouvy does not provide a public REST API — instead,
the platform uses a Hotwire Turbo-Stream protocol over standard HTTP POST
requests. The embedded client includes a full turbo-stream decoder that
translates these responses into typed Python dataclasses.

See [Architecture → Turbo-Stream Protocol](architecture/turbo-stream.md) for
technical details.
