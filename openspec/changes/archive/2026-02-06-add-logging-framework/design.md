## Context

The Rouvy API client (`rouvy_api_client`) is a Python library for interacting with the Rouvy API. Currently, there is no logging infrastructure - the client silently performs HTTP requests and only surfaces information through exceptions. This makes debugging authentication flows, tracking request/response cycles, and diagnosing production issues difficult.

The codebase uses `requests.Session` for HTTP operations and has a simple config-based initialization pattern. Adding logging should integrate naturally with existing Python logging conventions and allow client users to control log output through standard logging configuration.

## Goals / Non-Goals

**Goals:**

- Add structured logging using Python's standard `logging` module (avoid external dependencies)
- Log key events: authentication attempts, API requests/responses, errors
- Include contextual data: HTTP method, URL, status code, response time
- Allow configuration via standard logging methods (no custom config API)
- Maintain backward compatibility - logging is opt-in via standard logger configuration

**Non-Goals:**

- Custom logging framework or DSL - use Python's stdlib `logging`
- Log sanitization/PII filtering (user's responsibility to configure)
- Request/response body logging (security risk; can be added later if needed)
- Metrics or tracing integration (separate concern)

## Decisions

**Decision 1: Use Python's built-in `logging` module**

- **Rationale**: Standard library, zero dependencies, universally understood by Python developers
- **Alternatives considered**:
  - `structlog`: More powerful but adds dependency; overkill for this use case
  - Custom logger: Reinventing the wheel; harder to integrate with existing tools
- **Trade-off**: Less structured logging features, but better compatibility and simplicity

**Decision 2: Use module-level logger with conventional naming**

- **Rationale**: Create logger as `logging.getLogger(__name__)` in each module - follows Python conventions
- **Implementation**: `client.py` gets logger named `rouvy_api_client.client`
- **Benefit**: Users can configure different log levels per module (e.g., verbose auth logging)

**Decision 3: Log levels mapping**

- DEBUG: Individual request/response details, auth token refresh
- INFO: Successful authentication, high-level operations
- WARNING: Retries, fallback behaviors
- ERROR: Authentication failures, API errors (before raising exception)

**Decision 4: No logging of request/response bodies by default**

- **Rationale**: Security risk (credentials, PII). Users can enable via custom formatter if needed.
- **Risk Mitigation**: Document how to extend logging if bodies are needed for debugging

**Decision 5: Use `extra={}` for structured context**

- **Rationale**: Standard way to add structured data to log records
- **Example**: `logger.info("Request completed", extra={"status_code": 200, "duration_ms": 145})`
- **Benefit**: Compatible with JSON formatters for structured logging in production

## Risks / Trade-offs

**[Risk] Log verbosity impacts performance**  
→ Mitigation: Default to WARNING level; document performance considerations; lazy evaluation of log messages

**[Risk] Users unaware of logging capabilities**  
→ Mitigation: Add logging example to README with handler configuration

**[Risk] Sensitive data in logs (credentials, tokens)**  
→ Mitigation: Never log payload bodies or headers by default; document security best practices

**[Trade-off] Using stdlib logging vs structlog**  
→ Simpler integration and zero dependencies, but less ergonomic structured logging. Acceptable for this library's scope.
