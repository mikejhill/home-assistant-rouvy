## 1. Project setup

- [x] 1.1 Create Python package layout for the Rouvy API client
- [x] 1.2 Add `requests` dependency and document installation
- [x] 1.3 Add configuration model for base URL, credentials, and timeouts

## 2. Authentication session

- [x] 2.1 Implement login flow to obtain and store session state
- [x] 2.2 Implement session validity checks (expiry/invalid response)
- [x] 2.3 Implement re-authentication and single retry on unauthorized

## 3. Request helpers

- [x] 3.1 Implement authenticated request wrapper using shared session
- [x] 3.2 Define helper methods for the initial endpoint set
- [x] 3.3 Normalize API errors into structured client exceptions

## 4. Tests and docs

- [x] 4.1 Add tests for login, invalid session, and re-auth behavior
- [x] 4.2 Add tests for request helper success and error handling
- [x] 4.3 Write usage examples and configuration documentation
