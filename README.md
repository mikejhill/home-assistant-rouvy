# Rouvy API Client (Python)

A Python client for the Rouvy API with support for authentication, session management, and parsing of turbo-stream formatted responses.

## Features

- **Automatic Authentication**: Handles login and session initialization
- **Session Management**: Automatically re-authenticates on 401 responses
- **Incomplete Auth Handling**: Detects and resolves 202 redirect responses
- **Turbo-Stream Parser**: Decodes Remix turbo-stream formatted responses
- **Structured Logging**: Comprehensive debug and info-level logging with extra context

## Installation

For development, install the package in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

Or for production use (without test dependencies):

```bash
pip install -e .
```

This project uses a `src/` layout with the package located in `src/rouvy_api_client/`.

## Setup

Create a `.env` file in the project root with your Rouvy credentials:

```bash
cp .env.example .env
```

Then edit `.env` with your credentials:

```
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

The CLI tool can be run in multiple ways:

```bash
# Using the package module (recommended after installation)
python -m rouvy_api_client

# Using the convenience wrapper
python main.py

# Or if installed with pip, using the console script
rouvy-api
```

The main CLI tool supports multiple endpoints:

```bash
# Default: fetch user profile
python -m rouvy_api_client

# Fetch training zones
python main.py --endpoint user-settings/zones.data

# Fetch profile overview (large response)
python main.py --endpoint profile/overview.data

# Show raw decoded structure
python main.py --endpoint user-settings.data --raw

# Enable debug logging
python main.py --debug
```

Available options:

- `--endpoint, -e` - API endpoint to call (default: user-settings.data)
- `--raw` - Show raw decoded response instead of formatted output
- `--debug` - Enable debug logging
- `--log-level` - Set specific log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--set KEY=VALUE` - Update user settings (can be used multiple times)

### Updating User Settings

You can update user profile settings using the `--set` flag:

```bash
# Update weight
python main.py --set weight=86

# Update multiple fields at once
python main.py --set weight=86 --set height=178

# Change units system
python main.py --set units=IMPERIAL
```

**Supported fields:**

- `weight` - Weight in kg (METRIC) or lbs (IMPERIAL)
- `height` - Height in cm (METRIC) or inches (IMPERIAL)
- `units` - Measurement system: `METRIC` or `IMPERIAL`

The CLI automatically:

1. Fetches your current settings
2. Merges your updates with existing values
3. POSTs the complete update to the API
4. Displays the updated profile with changed fields highlighted

### Scripts

The `scripts/` directory contains additional utility and demo scripts:

- `demo_parser.py` - Comprehensive parser demo across multiple endpoints
- `test_endpoints.py` - Test different Rouvy API endpoints
- `debug_parser.py` - Debug utility for analyzing response structure

Run scripts with:

```bash
python scripts/demo_parser.py
```

### Programmatic Usage

```python
from rouvy_api_client import RouvyClient, RouvyConfig

# Initialize client
client = RouvyClient(
    RouvyConfig(
        email="you@example.com",
        password="your-password",
    )
)

# Fetch data
response = client.get("user-settings.data")
print(response.text)

# Update user settings
client.update_user_settings({
    "weight": 86,
    "height": 178
})

# Get updated settings
updated = client.get_user_settings()
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

The `rouvy_api_client` module provides a generic turbo-stream parser:

```python
from rouvy_api_client import parse_response, extract_user_profile

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

- [**docs/TURBO_STREAM.md**](docs/TURBO_STREAM.md) - Detailed explanation of the turbo-stream format discovery and implementation
- [**docs/samples/**](docs/samples/) - Sample API responses for reference

## Logging

The client uses Python's standard `logging` module. Enable logging by configuring
the `rouvy_api_client` logger or the `rouvy_api_client.client` module logger.

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

```
{"level":"DEBUG","name":"rouvy_api_client.client","message":"HTTP request completed","method":"GET","url":"https://riders.rouvy.com/user-settings.data","status_code":200,"duration_ms":12.34}
```

## Testing

```bash
python -m pytest -q
```
