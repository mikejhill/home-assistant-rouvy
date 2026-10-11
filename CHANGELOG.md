# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Count sensors (challenges, events, favorite routes, career level, friends,
  connected apps, total activities) have the `measurement` state class again,
  so Home Assistant keeps recording their long-term statistics and no longer
  raises "state class removed" repairs after upgrading from v1.

### Changed

- Tests check every numeric sensor has a state class, replay v1's long-term
  statistics metadata against v2 to catch upgrade repairs, and snapshot each
  sensor's statistics metadata. Development uses Python 3.14.6, which fixes
  `unittest.mock` autospec on lazily evaluated annotations.

## [2.0.1] - 2026-10-11

### Changed

- `main` requires the `ci-pass` check; the Release workflow pushes with a
  dedicated deploy key.
- The documentation site (https://mikejhill.github.io/home-assistant-rouvy/)
  is rebuilt from the current docs on every change to `main`; CI checks that
  it builds.

### Fixed

- Releases no longer attach a stray `default.gitignore` file.
- Numeric fields that arrive as strings such as `"INF"` or `"NaN"` are
  treated as missing instead of crashing the parser (found by property tests).

## [2.0.0] - 2026-10-10

### Fixed

- Login works again. Rouvy's firewall now rejects generic HTTP library user
  agents and removed the `/_root.data` route the old client called after
  login; the client now identifies itself, verifies the session explicitly,
  and reports wrong passwords, disabled accounts, rate limiting, firewall
  blocks, and sign-in flow changes as distinct errors.
- Weekly sensors use the week containing today (previously the first week of
  the month) and sum all activity types.
- `update_profile` no longer fills missing gender, birth date, or country with
  invented defaults, and sends the timezone and language Rouvy's profile form
  now requires.
- `update_timezone` uses Rouvy's profile form (the old timezone route is gone).
- Favorite routes come from the favourites collection; events are read from
  Rouvy's current events page (the old parser found none). Upcoming events and
  Next event now track events you have joined.
- Weekly stats parse Rouvy's display-format week dates.
- Sensors become unavailable only when their data could not be fetched; a
  sensor with no value (for example, no joined event) shows unknown.
- The CLI no longer crashes on Windows consoles when titles contain emoji.

### Changed

- Rebuilt from scratch: typed async library `rouvy_api` (spec-correct
  turbo-stream decoder, key-based parsers), thin Home Assistant integration,
  and CLI. Entity unique ids and action names are unchanged.
- Requires Home Assistant 2026.10 or newer.
- Reauthentication asks only for the password; added a reconfigure step.
- Optional data sections are fetched concurrently and keep their last value on
  failure.

### Added

- Month- and year-to-date distance, ride time, and elevation sensors.
- Diagnostics download with personal data redacted.
- Daily contract canary against rouvy.com, property-based, performance, UX
  consistency, and end-to-end tests.
- Release workflow (`Actions -> Release`) driven by `scripts/release.py`, with
  a downloadable `rouvy.zip` on every GitHub release.
- Dependabot now updates `uv.lock`; the pre-commit hook runs ruff and the
  vendoring check.

### Removed

- The `team` field of `update_profile` (Rouvy no longer lets riders edit it).
- `update_profile` fields are now snake_case (`username`, `first_name`,
  `last_name`, `country`, `date_of_birth`, `account_privacy`), as Home
  Assistant requires.

- Live tests that modified the account; live tests are now read-only.
- The generated MkDocs command reference (superseded by `rouvy-api --help`).

## 0.1.0 (unreleased prototype)

### Added

- Typed data models: `UserProfile`, `TrainingZones`, `ConnectedApp`, `Activity`, `ActivitySummary`
- CLI with subcommands: `profile`, `zones`, `apps`, `activities`, `set`, `raw`
- Full turbo-stream decoder with indexed reference resolution
- Synchronous HTTP client with automatic session-based authentication
- Native Home Assistant integration (HACS-compatible) with sensors and write services
- Async `aiohttp` API client for Home Assistant
- Comprehensive test suite (274 tests, 80%+ coverage)
- CI workflow with ruff, ty, pytest matrix, and markdown lint
- Release workflow with automated versioning and CHANGELOG promotion
