# ADR 0001: Vendor the library into the integration

- Status: accepted
- Date: 2026-10-10

## Context

Home Assistant installs integration dependencies from PyPI via
`manifest.json` `requirements`. HACS installs only `custom_components/rouvy`.
The library should live in `src/rouvy_api` so it can be tested, typed, and
used by the CLI independently of Home Assistant.

## Decision

`src/rouvy_api` is the single source of truth. `scripts/vendor_library.py`
copies it (without `cli/`) into `custom_components/rouvy/rouvy_api`, rewriting
absolute imports to `custom_components.rouvy.rouvy_api`. CI runs
`poe vendor-check` and fails if the copy is stale. Ruff, ty, and coverage
ignore the generated copy.

## Consequences

- No PyPI publishing is needed for the integration to work, and HACS installs
  stay self-contained.
- The library can be published to PyPI later; switching the integration to a
  `requirements` entry is then a one-line manifest change plus deleting the copy.
- Contributors must run `uv run poe vendor` (part of `poe fix`) after library
  changes.
