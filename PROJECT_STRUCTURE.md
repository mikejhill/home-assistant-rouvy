# Project Structure

This document describes the organization of the Rouvy API Client project.

## Directory Layout

```
rouvy-api/
├── main.py                     # Convenience CLI wrapper (imports from package)
│
├── src/                        # Source code directory (src layout)
│   └── rouvy_api_client/       # Core API client library (pure Python, no HASS deps)
│       ├── __init__.py         # Module exports
│       ├── __main__.py         # CLI entry point (python -m rouvy_api_client)
│       ├── client.py           # HTTP client with authentication
│       ├── config.py           # Configuration dataclass
│       ├── errors.py           # Custom exception classes
│       └── parser.py           # Turbo-stream decoder
│
├── integrations/               # Platform-specific integrations (separate from core)
│   └── home-assistant/         # Home Assistant / AppDaemon integration
│       ├── README.md           # HASS integration documentation
│       ├── pyproject.toml      # HASS integration package config
│       └── appdaemon/          # AppDaemon app module
│           ├── __init__.py     # Integration exports
│           └── rouvy_app.py    # AppDaemon Hass app
│
├── scripts/                    # Utility and example scripts
│   ├── demo_parser.py          # Parser demonstrations
│   ├── debug_parser.py         # Debug utilities
│   └── test_endpoints.py       # Endpoint discovery tool
│
├── docs/                       # Documentation and reference materials
│   ├── TURBO_STREAM.md         # Turbo-stream format analysis
│   └── samples/                # Sample API responses for reference
│       ├── sample_user-settings_data.txt
│       ├── sample_user-settings_zones_data.txt
│       ├── sample_user-settings_connected-apps_data.txt
│       ├── sample_profile_overview_data.txt
│       └── sample_resources_activities-pagination_data.txt
│
├── tests/                      # Unit tests for core library
│   ├── __init__.py
│   └── test_client.py
│
├── .github/                    # GitHub workflows and configuration
├── .env.example                # Example environment variables
├── pyproject.toml              # Core package configuration (no HASS dependencies)
└── README.md                   # Project documentation

```

**Note:** The project uses a modern `src/` layout with `pyproject.toml` for package management. The core API client library has zero Home Assistant dependencies. The package can be installed in editable mode using `pip install -e .` or `pip install -e ".[dev]"` for development dependencies.

## Architecture: Clean Separation of Concerns

This project follows industry best practices by cleanly separating the core API client from platform-specific integrations:

### Core API Client (`src/rouvy_api_client/`)
- **Pure Python library** with zero dependencies on Home Assistant, AppDaemon, or any platform-specific code
- Can be used in any Python project, web service, data pipeline, or automation tool
- Installable via `pip install -e .` or published to PyPI as `rouvy-api-client`
- Dependencies: Only `requests` and `python-dotenv`

### Home Assistant Integration (`integrations/home-assistant/`)
- **Separate optional integration** that depends on the core library
- Only needed for Home Assistant users
- Has its own `pyproject.toml` with AppDaemon dependencies
- Can be installed separately via `pip install -e integrations/home-assistant/`
- Dependencies: `rouvy-api-client` + `appdaemon`

This separation provides several benefits:
1. **Clarity**: Clear boundary between API client and HASS integration
2. **Reusability**: Core library can be used in non-HASS contexts
3. **Maintainability**: Changes to HASS integration don't affect core library
4. **Dependencies**: Core library stays lightweight with minimal dependencies
5. **Testing**: Core library can be tested independently

## Core Library (src/rouvy_api_client/)

The main API client library is in the `src/rouvy_api_client/` directory and provides:

- **`RouvyClient`** - HTTP client with automatic authentication
- **`RouvyConfig`** - Configuration dataclass
- **`TurboStreamDecoder`** - Decoder for turbo-stream formatted responses
- **`parse_response()`** - Generic turbo-stream parser
- **`extract_user_profile()`** - Specialized user profile extractor

## Primary CLI (main.py)

The `main.py` file in the root directory is the primary command-line interface for making API calls:

- Supports configurable endpoint selection via `--endpoint` argument
- Provides formatted output for known endpoints (user profile, zones, apps)
- Falls back to generic parsing for unknown endpoints
- Offers raw decoded output with `--raw` flag
- Will evolve to become the full-featured CLI for the API client

## Scripts (scripts/)

Utility and example scripts that demonstrate usage:

- **`demo_parser.py`** - Comprehensive parser demonstration with multiple endpoints
- **`test_endpoints.py`** - Script to test and discover API endpoints
- **`debug_parser.py`** - Debug tool for analyzing response structure

All scripts automatically adjust the import path to load the `rouvy_api_client` module from the parent directory.

## Documentation (docs/)

Reference and analysis materials:

- **`TURBO_STREAM.md`** - Complete analysis of the turbo-stream format used by Rouvy
- **`samples/`** - Real sample responses from various endpoints for offline analysis

## Integrations (integrations/)

Platform-specific integrations that depend on the core library:

### Home Assistant / AppDaemon (integrations/home-assistant/)

AppDaemon integration for Home Assistant users:

- **`appdaemon/rouvy_app.py`** - AppDaemon app that listens for triggers and calls the API
- **`README.md`** - Complete documentation for HASS integration setup and usage
- **`pyproject.toml`** - Package configuration with AppDaemon dependencies

**Installation:**
```bash
# Install core library first
pip install -e .

# Then install HASS integration
pip install -e integrations/home-assistant/
```

See [integrations/home-assistant/README.md](integrations/home-assistant/README.md) for detailed setup and configuration instructions.

## Development

- **`tests/`** - Unit tests for the client library
- **`requirements-dev.txt`** - Development dependencies (linters, test runners, etc.)
- **`.github/`** - GitHub Actions workflows and configuration
- **`.env.example`** - Template for `.env` file with required environment variables

## Running Examples

To use the primary CLI interface:

```bash
# Fetch user profile (default)
python main.py

# Fetch training zones
python main.py --endpoint user-settings/zones.data

# Fetch with debug logging
python main.py --endpoint profile/overview.data --debug
```

To run utility scripts:

```bash
# Comprehensive parser demonstrations
python scripts/demo_parser.py

# Test and discover available endpoints
python scripts/test_endpoints.py
```

## Adding New Code

When adding new functionality:

1. **API client improvements** → `rouvy_api_client/client.py`
2. **Data parsing logic** → `rouvy_api_client/parser.py`
3. **New examples** → Create scripts in `scripts/`
4. **Tests** → Add to `tests/`
5. **Documentation** → Update in `docs/` with reference materials
