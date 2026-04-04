# Project Structure

This document describes the organization of the Home Assistant Rouvy integration project.

## Directory Layout

```text
home-assistant-rouvy/
├── custom_components/          # Home Assistant integration (HACS-compatible)
│   └── rouvy/
│       ├── __init__.py         # Integration setup + service registration
│       ├── api.py              # Async aiohttp API client
│       ├── config_flow.py      # UI config flow (email/password)
│       ├── const.py            # Domain, logger, config constants
│       ├── coordinator.py      # DataUpdateCoordinator (hourly polling)
│       ├── data.py             # RouvyData runtime dataclass
│       ├── entity.py           # Base RouvyEntity class
│       ├── manifest.json       # HA + HACS manifest
│       ├── sensor.py           # Sensor entities (weight, height, FTP, max HR, etc.)
│       ├── services.yaml       # Service definitions
│       ├── strings.json        # UI strings
│       ├── translations/
│       │   └── en.json         # English translations
│       └── api_client/         # Embedded API client library (pure Python, no HA deps)
│           ├── __init__.py     # Module exports
│           ├── __main__.py     # CLI entry point with subcommands
│           ├── client.py       # HTTP client with authentication + typed accessors
│           ├── config.py       # Configuration dataclass
│           ├── errors.py       # Custom exception classes
│           ├── models.py       # Frozen dataclass models (UserProfile, TrainingZones, etc.)
│           └── parser.py       # Turbo-stream decoder + typed extraction functions
│
├── scripts/                    # Utility and example scripts
│   ├── demo_parser.py          # Parser demonstrations
│   ├── debug_parser.py         # Debug utilities
│   └── test_endpoints.py       # Endpoint discovery tool
│
├── docs/                       # Documentation and reference materials
│   ├── architecture/           # Architecture and design documentation
│   │   ├── project-structure.md  # This file
│   │   └── turbo-stream.md     # Turbo-stream format analysis
│   └── private-samples/        # Sample API responses (git-ignored, local only)
│
├── tests/                      # Unit and integration tests
│
├── .python-version             # Python version for uv toolchain
├── hacs.json                   # HACS repository configuration
├── pyproject.toml              # Package configuration (hatchling build)
├── uv.lock                     # Dependency lock file
└── README.md                   # Project documentation
```

## Architecture

The project uses a monorepo layout with the API client library embedded inside the Home Assistant integration as a sub-package (`api_client/`). This ensures the HA integration is fully self-contained for HACS deployment while the CLI shares the same code.

### API Client (`custom_components/rouvy/api_client/`)

- **Pure Python library** with zero HA dependencies
- Sync HTTP client using `requests` for CLI usage
- Typed frozen dataclass models for all API response types
- Full turbo-stream decoder with indexed reference resolution
- Dependencies: `requests`, `python-dotenv`

### Home Assistant Integration (`custom_components/rouvy/`)

- **Native HA integration** using ConfigFlow + DataUpdateCoordinator
- Async HTTP client using `aiohttp` (provided by HA)
- Uses parser, models, and errors from the embedded `api_client` sub-package
- Installable via HACS as a custom repository
- Exposes sensors and write services for weight/height/settings updates

### CLI (`custom_components/rouvy/api_client/__main__.py`)

- Subcommand-based interface: `profile`, `zones`, `apps`, `activities`, `set`, `raw`
- Backward compatible with legacy `--endpoint`, `--set`, `--raw` flags
- Uses typed models for formatted output

## Testing

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=custom_components -v
```
