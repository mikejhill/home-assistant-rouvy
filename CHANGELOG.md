# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
