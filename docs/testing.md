# Testing strategy

| Layer | Location | What it proves | Runs |
| --- | --- | --- | --- |
| Static | `poe lint`, `poe typecheck` | Style, bugbear and bandit rules, docstrings, cyclomatic complexity ≤ 8, strict types (every ty rule is an error) | Every PR |
| Unit | `tests/lib` | Decoder, payload navigation, parsers (on sanitized real captures), auth mapping, client behaviour | Every PR |
| Property | `tests/property` | Hypothesis round-trips: encode → decode is lossless; the decoder never raises anything but `RouvyResponseError` | Every PR |
| CLI | `tests/cli` | Parsing, output formats, exit codes, friendly errors | Every PR |
| Home Assistant | `tests/ha` | Config flow (UX errors, reauth, reconfigure), setup/unload, coordinator resilience, every sensor value, every action, diagnostics redaction | Every PR |
| UX consistency | `tests/ha/test_metadata.py` | Every sensor, action, field, error, and exception has English text and an icon; versions agree | Every PR |
| Upgrade compatibility | `tests/ha/test_upgrade.py`, `tests/ha/__snapshots__` | v2 raises no statistics repairs (state class removed, unit or mean type changed) against the long-term statistics v1 recorded; any change to a sensor's class, unit, or category shows up as a snapshot diff | Every PR |
| End to end | `tests/ha/test_e2e_journey.py`, `tests/e2e` | Full journeys against an in-process fake Rouvy portal over real HTTP: onboarding, actions, session expiry, password change, reauth, removal; CLI as a subprocess | Every PR |
| Performance | `tests/perf` | Benchmarks and hard budgets for decoding and parsing; concurrent fetching | Every PR |
| Contract | `tests/contract` | Live, account-free canaries: firewall accepts our user agent, login errors still parse, anonymous reads still redirect | Daily |
| Live | `tests/live` | Read-only smoke test with a real account | Weekly / manual |
| Release script | `tests/scripts` | Version bumps and CHANGELOG promotion used by the release workflow | Every PR |

## Fake portal

`tests/support/fake_rouvy.py` is an aiohttp app that reproduces the behaviours
the client depends on: firewall rejection of library user agents, form-error
logins, cookie sessions, sign-in redirects, expiry, failures, and latency.
`tests/support/turbo_encoder.py` is a turbo-stream encoder used to build
payloads and to drive property tests.

## Fixtures

`tests/fixtures/*.txt` are real Rouvy responses with personal data removed by
`scripts/sanitize_fixture.py`. Never commit unsanitized captures; keep them in
the git-ignored `docs/private-samples/`.

## Live tests

`poe live` reads `ROUVY_TEST_EMAIL` and `ROUVY_TEST_PASSWORD` from the
environment or from `.env` (via python-dotenv, so passwords with shell
characters are safe). The module shares one login: Rouvy throttles repeated
logins with HTTP 429 after a few attempts in quick succession, and locks out
an account for several minutes after repeated wrong passwords.

## Commands

```bash
uv run poe check
```

```bash
uv run poe contract
```

```bash
ROUVY_TEST_EMAIL=you@example.com ROUVY_TEST_PASSWORD=... uv run poe live
```
