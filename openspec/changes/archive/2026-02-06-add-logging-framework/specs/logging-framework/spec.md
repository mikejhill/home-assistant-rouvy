## ADDED Requirements

### Requirement: Logger initialization
The system SHALL create a module-level logger using Python's standard logging module in each source file that requires logging.

#### Scenario: Logger created in client module
- **WHEN** the `client.py` module is imported
- **THEN** a logger instance is created using `logging.getLogger(__name__)`
- **THEN** the logger name is `rouvy_api_client.client`

### Requirement: Authentication logging
The system SHALL log authentication attempts and outcomes at appropriate levels.

#### Scenario: Successful authentication
- **WHEN** `login()` method successfully authenticates
- **THEN** an INFO-level log is emitted with message "Authentication successful"

#### Scenario: Failed authentication
- **WHEN** `login()` method receives HTTP 4xx response
- **THEN** an ERROR-level log is emitted with message "Authentication failed" and status code before raising exception

#### Scenario: Authentication retry
- **WHEN** a 401 response triggers re-authentication
- **THEN** a DEBUG-level log is emitted with message "Re-authenticating due to 401 response"

### Requirement: Request logging
The system SHALL log HTTP requests with method, URL, and outcome.

#### Scenario: Successful request
- **WHEN** an API request completes successfully
- **THEN** a DEBUG-level log is emitted including HTTP method, URL path, and status code

#### Scenario: Request with timing
- **WHEN** an API request completes
- **THEN** the log record includes response time in milliseconds as structured data

#### Scenario: Failed request
- **WHEN** an API request returns HTTP 4xx or 5xx
- **THEN** an ERROR-level log is emitted with status code before raising exception

### Requirement: Structured logging context
The system SHALL support structured logging using the `extra` parameter for contextual data.

#### Scenario: Request log with context
- **WHEN** logging an API request
- **THEN** the log includes structured data in `extra` dict: `{"method": "GET", "url": "/path", "status_code": 200, "duration_ms": 145}`

### Requirement: Log level configuration
Users SHALL be able to control log verbosity using standard Python logging configuration without code changes.

#### Scenario: Module-specific log level
- **WHEN** user configures logger `rouvy_api_client.client` to DEBUG level
- **THEN** all DEBUG, INFO, WARNING, and ERROR logs from client module are emitted

#### Scenario: Library-wide log level
- **WHEN** user configures logger `rouvy_api_client` to WARNING level
- **THEN** only WARNING and ERROR logs from all library modules are emitted

### Requirement: Sensitive data protection
The system SHALL NOT log request/response bodies or authentication headers by default to protect sensitive data.

#### Scenario: Request logging excludes payload
- **WHEN** logging an API request with JSON body
- **THEN** the log does NOT include the request body content

#### Scenario: Authentication logging excludes credentials
- **WHEN** logging authentication attempt
- **THEN** the log does NOT include email or password values
