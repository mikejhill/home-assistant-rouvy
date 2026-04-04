# Home Assistant Integration Guide

This guide covers setting up and testing the Rouvy integration for Home Assistant, including HACS installation and manual development setup.

## Overview

The Rouvy integration provides:

- **Sensors** — Weight (kg), Height (cm), FTP (watts), Max Heart Rate (bpm), Units, Display Name
- **Services** — `rouvy.update_weight`, `rouvy.update_height`, `rouvy.update_settings`
- **Polling** — Automatic hourly data refresh via DataUpdateCoordinator
- **Config Flow** — UI-based setup with email/password credentials

## HACS Installation (Recommended)

[HACS](https://hacs.xyz/) is the Home Assistant Community Store. It manages custom integrations.

### Prerequisites

1. A running Home Assistant instance (2024.1 or later recommended)
2. [HACS installed](https://hacs.xyz/docs/use/) in your HA instance

### Steps

1. Open Home Assistant and go to **HACS** in the sidebar
2. Click the **⋮** menu (top right) → **Custom repositories**
3. Enter the repository URL: `https://github.com/mikejhill/rouvy-api`
4. Select category: **Integration**
5. Click **Add**
6. The **Rouvy** integration now appears in HACS — click **Download**
7. **Restart Home Assistant** (Settings → System → Restart)
8. Go to **Settings** → **Devices & Services** → **Add Integration**
9. Search for **Rouvy** and select it
10. Enter your Rouvy account email and password
11. The integration creates a device with sensors for your profile data

### What HACS Does

HACS clones the `custom_components/rouvy/` directory from this repository into your HA `config/custom_components/` directory. The `hacs.json` file at the repository root tells HACS where to find the integration.

Key files HACS uses:

- `hacs.json` — Repository metadata (`render_readme: true` means the README is shown in HACS)
- `custom_components/rouvy/manifest.json` — Integration metadata (name, domain, version, requirements)

## Manual Installation (Development)

For development or testing without HACS.

### Steps

1. Copy the `custom_components/rouvy/` directory into your Home Assistant `config/custom_components/` directory:

   ```bash
   # From this repository root
   cp -r custom_components/rouvy /path/to/homeassistant/config/custom_components/
   ```

2. Install the core library dependency. The `manifest.json` lists `rouvy-api-client==0.1.0` as a requirement. Since this package is not yet on PyPI, install it manually in the HA Python environment:

   ```bash
   # Find the HA Python environment
   # For HA OS / Supervised: use the HA terminal add-on
   # For HA Core: activate the venv

   pip install /path/to/rouvy-api  # or pip install -e /path/to/rouvy-api
   ```

3. Restart Home Assistant
4. Add the integration via **Settings** → **Devices & Services** → **Add Integration** → **Rouvy**

### Development with HA Core (Docker)

For a full development environment:

```bash
# Clone Home Assistant core
git clone https://github.com/home-assistant/core.git ha-core
cd ha-core

# Create and activate venv
python3 -m venv venv
source venv/bin/activate

# Install HA core requirements
pip install -e ".[dev]"

# Symlink the Rouvy integration
ln -s /path/to/rouvy-api/custom_components/rouvy config/custom_components/rouvy

# Install the core library
pip install -e /path/to/rouvy-api

# Run HA
hass -c config
```

## Testing the Integration

### Verify Sensors

After adding the integration, check that sensors are created:

1. Go to **Settings** → **Devices & Services** → **Rouvy**
2. Click the device — you should see these entities:
   - `sensor.rouvy_weight` — Your weight in kg
   - `sensor.rouvy_height` — Your height in cm
   - `sensor.rouvy_ftp` — Functional Threshold Power in watts
   - `sensor.rouvy_max_heart_rate` — Max heart rate in bpm
   - `sensor.rouvy_units` — Unit system (METRIC/IMPERIAL)
   - `sensor.rouvy_name` — Display name

### Test Services

Open **Developer Tools** → **Services** and test each service:

#### Update Weight

```yaml
service: rouvy.update_weight
data:
  weight: 80.0
```

#### Update Height

```yaml
service: rouvy.update_height
data:
  height: 178.0
```

#### Update Arbitrary Settings

```yaml
service: rouvy.update_settings
data:
  settings:
    weight: 80
    height: 178
    units: METRIC
```

### Automations

Example automation that syncs weight from another source to Rouvy:

```yaml
automation:
  - alias: "Sync weight to Rouvy"
    trigger:
      - platform: state
        entity_id: sensor.withings_weight
    action:
      - service: rouvy.update_weight
        data:
          weight: "{{ states('sensor.withings_weight') | float }}"
```

## Troubleshooting

### Integration Not Appearing

- Ensure you restarted Home Assistant after installing
- Check that `custom_components/rouvy/` exists in your HA config directory
- Check the HA logs for import errors: **Settings** → **System** → **Logs**

### Authentication Fails

- Verify your Rouvy credentials work at [riders.rouvy.com](https://riders.rouvy.com)
- Check that your account is not locked or pending verification
- Review HA logs for specific error messages

### Sensors Show "Unknown"

- The integration polls Rouvy hourly. Wait for the first refresh or manually trigger one:
  **Developer Tools** → **Services** → `homeassistant.update_entity`
- Check HA logs for API errors (Rouvy may be temporarily unavailable)

### Debug Logging

Enable debug logging for the integration:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.rouvy: debug
```

Restart HA and check the logs for detailed request/response information.

## Architecture Notes

The integration is fully self-contained within `custom_components/rouvy/`:

1. **Embedded API client** (`custom_components/rouvy/api_client/`) — Pure Python, sync HTTP client, typed models, turbo-stream parser. No HA dependencies.
2. **HA integration** (`custom_components/rouvy/`) — Async `aiohttp` client, ConfigFlow, DataUpdateCoordinator, sensor entities, services.

The HA integration does NOT import the sync client. It has its own async API client (`api.py`) that uses `aiohttp` (provided by HA) and imports the parser and models from the embedded `api_client` sub-package.

## HACS Repository Requirements

For this repository to work with HACS, these conditions must be met:

- `hacs.json` exists at repository root with `{"name": "Rouvy", "render_readme": true}`
- `custom_components/rouvy/manifest.json` exists with valid HA manifest fields
- The `domain` in `manifest.json` matches the directory name (`rouvy`)
- `config_flow: true` enables the UI setup wizard
- The repository is public on GitHub
