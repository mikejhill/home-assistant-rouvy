## Why

The project needs a Python client to authenticate with the Rouvy API and keep a valid login state so downstream API calls are reliable. This enables automated interactions without re-implementing auth flows in every script.

## What Changes

- Add a Python client library for the Rouvy API with a clear public interface.
- Add login and session state handling so requests reuse valid credentials.
- Add request helpers for a defined set of Rouvy API endpoints.

## Capabilities

### New Capabilities
- `rouvy-auth-session`: Authenticate, store, and refresh login state for the Rouvy API.
- `rouvy-api-requests`: Make authenticated requests to selected Rouvy API endpoints.

### Modified Capabilities

## Impact

- New Python package/modules under the repository.
- New HTTP dependency for API calls (e.g., `httpx` or `requests`).
- New configuration and secrets handling for credentials.
