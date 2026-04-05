"""Integration tests for the Rouvy API.

⚠️  WARNING: These tests run against the REAL Rouvy API. They will modify
account settings (weight, height, FTP, zones, timezone, username, etc.)
and attempt to restore original values on completion.

DO NOT run these tests with a real user account. Use a dedicated test
account with no valuable data. Restoration is best-effort and may fail
if tests are interrupted.

Required environment variables:
    ROUVY_TEST_EMAIL    — Test account email address
    ROUVY_TEST_PASSWORD — Test account password
"""
