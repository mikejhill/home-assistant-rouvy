# Rouvy API - Home Assistant Integration

This directory contains the Home Assistant / AppDaemon integration for the Rouvy API Client.

## Overview

The Home Assistant integration provides an AppDaemon app that allows you to fetch data from the Rouvy API and expose it in Home Assistant.

## Installation

### Prerequisites

1. Install the core Rouvy API client library:
   ```bash
   pip install rouvy-api-client
   ```
   
   Or install from the repository root:
   ```bash
   cd /path/to/rouvy-api
   pip install -e .
   ```

2. Install AppDaemon dependencies:
   ```bash
   pip install appdaemon>=4.4.0
   ```

### Setup

1. Copy the `appdaemon/` directory to your AppDaemon apps directory
2. Configure the app in your `apps.yaml`

## Configuration

Add the following to your AppDaemon `apps.yaml`:

```yaml
rouvy_api:
  module: appdaemon.rouvy_app
  class: RouvyApp
  sensor: sensor.dummy
  endpoint: user-settings.data
  target_sensor: sensor.rouvy_api_status
  command_sensor: input_text.appdaemon_app_trigger
  service_domain: rouvy_api
  service_name: fetch
  email: !secret rouvy_email
  password: !secret rouvy_password
```

## Usage

### Method 1: Pseudo-service (RECOMMENDED)

Call from automations or scripts:

```yaml
service: rouvy_api.fetch
data:
  endpoint: user-settings/zones.data
```

**Note:** This service won't appear in the HA UI service picker, but it works when called. You can wrap it in a script for better UI integration.

### Method 2: JSON Command Sensor

Write JSON to the configured text helper:

```json
{ "app_name": "rouvy_api", "endpoint": "user-settings.data" }
```

### Method 3: Sensor State Change

The app listens to state changes on the configured sensor and triggers API calls.

## Creating a Home Assistant Script Wrapper

For better UI integration with type validation:

```yaml
# scripts.yaml
rouvy_fetch_data:
  alias: "Rouvy: Fetch Data"
  fields:
    endpoint:
      description: "API endpoint to fetch"
      example: "user-settings/zones.data"
      required: true
  sequence:
    - service: rouvy_api.fetch
      data:
        endpoint: "{{ endpoint }}"
```

## Dependencies

- **rouvy-api-client**: The core API client library (must be installed separately)
- **appdaemon**: AppDaemon framework (>=4.4.0)

## Architecture

This integration is designed to be cleanly separated from the core API client library:

- **Core Library** (`rouvy-api-client`): Pure Python API client with zero Home Assistant dependencies
- **HASS Integration** (this directory): AppDaemon-specific code that depends on the core library

This separation follows industry best practices:
- The core library can be used independently in any Python project
- The HASS integration is optional and only needed for Home Assistant users
- Dependencies are clearly separated (no HASS dependencies in the core library)

## Available Endpoints

- `user-settings.data` - User profile and preferences
- `user-settings/zones.data` - Power and heart rate training zones
- `user-settings/connected-apps.data` - Connected third-party apps
- `profile/overview.data` - Profile overview with recent activities
- `resources/activities-pagination.data` - Paginated activity list

## Troubleshooting

### Service not appearing in UI

This is expected behavior. The pseudo-service approach uses AppDaemon's event listening to simulate a service. Create a script wrapper (see above) for UI integration.

### Authentication errors

Ensure your Rouvy credentials are correctly set in the configuration or environment variables:
- `ROUVY_EMAIL`
- `ROUVY_PASSWORD`

### Import errors

Make sure the core `rouvy-api-client` library is installed in the same Python environment as AppDaemon.

## License

This integration follows the same license as the main Rouvy API Client project.
