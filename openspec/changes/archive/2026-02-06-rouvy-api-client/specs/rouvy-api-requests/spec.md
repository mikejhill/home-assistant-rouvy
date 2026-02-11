## ADDED Requirements

### Requirement: Client makes authenticated API requests
The client SHALL send authenticated requests to the configured Rouvy API endpoints using the active session.

#### Scenario: Authenticated request succeeds
- **WHEN** the client calls a supported endpoint with a valid session
- **THEN** the API response is returned to the caller

### Requirement: Client exposes request helpers for defined endpoints
The client SHALL provide helper methods for a defined set of Rouvy API endpoints.

#### Scenario: Helper method invoked
- **WHEN** a caller invokes a supported helper method
- **THEN** the client constructs and sends the correct API request

### Requirement: Client reports API errors consistently
The client SHALL surface API errors with status code and response payload.

#### Scenario: API returns error
- **WHEN** the API responds with a non-success status
- **THEN** the client raises a structured error containing the status and payload
