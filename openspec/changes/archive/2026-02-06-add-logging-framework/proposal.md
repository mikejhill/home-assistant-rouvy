## Why

The Rouvy API client currently has no logging infrastructure, making it difficult to debug authentication flows, track API requests, or diagnose failures in production environments. Adding structured logging will improve observability and developer experience.

## What Changes

- Add a logging framework with configurable log levels (DEBUG, INFO, WARNING, ERROR)
- Log authentication attempts, API requests/responses, and error conditions
- Support structured logging with contextual information (request IDs, status codes, timing)
- Allow users to configure log output destination and format
- Add dependency on a standard Python logging library (e.g., `structlog` or Python's built-in `logging`)

## Capabilities

### New Capabilities

- `logging-framework`: Structured logging infrastructure with configurable levels, formats, and handlers for tracking API interactions, authentication, and errors

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- **Code**: All methods in `RouvyClient` class will be instrumented with logging calls
- **Dependencies**: Add logging library to `requirements.txt`
- **Configuration**: New configuration options for log level and output format
- **Performance**: Minimal overhead (<5ms per request); configurable to disable for production
- **Breaking Changes**: None - logging is additive and opt-in
