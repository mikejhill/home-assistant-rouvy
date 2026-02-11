## 1. Setup

- [x] 1.1 Ensure Python's `logging` module is available (stdlib, no dependency changes needed)
- [x] 1.2 Add logging configuration example to README.md

## 2. Core Implementation

- [x] 2.1 Add module-level logger to `rouvy_api_client/client.py` using `logging.getLogger(__name__)`
- [x] 2.2 Add INFO-level log in `login()` method on successful authentication
- [x] 2.3 Add ERROR-level log in `login()` method on authentication failure (before raising exception)
- [x] 2.4 Add DEBUG-level log in `request()` method when re-authenticating due to 401
- [x] 2.5 Add DEBUG-level logs in `_send_request()` for each HTTP request with method, URL, and status code
- [x] 2.6 Add response timing measurement and include `duration_ms` in log extra data
- [x] 2.7 Add ERROR-level log in `request()` method when API returns 4xx/5xx (before raising exception)
- [x] 2.8 Ensure structured logging context uses `extra={}` dict for contextual data (status_code, duration_ms, method, url)

## 3. Testing

- [x] 3.1 Add test case verifying logger is initialized with correct name (`rouvy_api_client.client`)
- [x] 3.2 Add test case for successful authentication logging at INFO level
- [x] 3.3 Add test case for failed authentication logging at ERROR level
- [x] 3.4 Add test case for request logging at DEBUG level with structured context
- [x] 3.5 Add test case verifying sensitive data (credentials, bodies) are NOT logged
- [x] 3.6 Verify logs can be configured via Python's logging config (manual test)

## 4. Documentation

- [x] 4.1 Add logging configuration example to README.md showing how to enable DEBUG logging
- [x] 4.2 Document security considerations: no request/response bodies logged by default
- [x] 4.3 Add example of structured logging output format
