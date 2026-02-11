## ADDED Requirements

### Requirement: Client can authenticate with Rouvy
The client SHALL authenticate with the Rouvy API using configured credentials and establish an authenticated session.

#### Scenario: Successful login
- **WHEN** valid credentials are provided to the login operation
- **THEN** the client stores an authenticated session for subsequent requests

### Requirement: Client detects expired authentication
The client SHALL detect expired or invalid authentication before or during requests.

#### Scenario: Session expired
- **WHEN** the stored session is expired or rejected by the API
- **THEN** the client marks the session invalid

### Requirement: Client re-authenticates on invalid session
The client SHALL re-authenticate once when a request fails due to invalid authentication.

#### Scenario: Request returns unauthorized
- **WHEN** an authenticated request returns an unauthorized response
- **THEN** the client re-authenticates and retries the request once
