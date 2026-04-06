# Getting Started

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### As a Home Assistant Integration (HACS)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations → Custom Repositories**
3. Add `mikejhill/home-assistant-rouvy` as an **Integration**
4. Install the **Rouvy** integration
5. Restart Home Assistant
6. Navigate to **Settings → Devices & Services → Add Integration**
7. Search for **Rouvy** and enter your credentials

### As a CLI Tool

```bash
# Install from the repository
uv tool install .

# Or install in development mode
git clone https://github.com/mikejhill/home-assistant-rouvy.git
cd home-assistant-rouvy
uv sync
```

## CLI Configuration

Create a `.env` file in the project root (or set environment variables):

```ini
ROUVY_EMAIL=your-email@example.com
ROUVY_PASSWORD=your-password
```

## First Commands

```bash
# View your profile (default command)
rouvy-api profile

# View training zones
rouvy-api zones

# Get JSON output for scripting
rouvy-api profile --json | jq .weight_kg

# Update your weight
rouvy-api set-weight --weight 86.5

# Enable debug logging
rouvy-api profile --verbose
```

## Global Flags

All commands support these flags:

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON instead of formatted text |
| `--verbose` | Enable debug logging |
| `--log-level LEVEL` | Set log level (DEBUG, INFO, WARNING, ERROR) |

## Next Steps

- Browse the [CLI Reference](reference/commands/index.md) for all 23 commands
- See the [Schema Reference](reference/schemas/index.md) for JSON output formats
- Read the [Home Assistant Setup Guide](guides/home-assistant-setup.md) for
  integration-specific configuration
