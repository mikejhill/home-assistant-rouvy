# Project charter

## Purpose

Bring a rider's [Rouvy](https://rouvy.com/) indoor-cycling account into Home
Assistant: show training data as sensors, and let automations change Rouvy
settings or query Rouvy data. Rouvy has no public API, so the project talks to
the same Remix "single fetch" routes (`*.data`, turbo-stream encoded) that the
riders.rouvy.com web app uses.

## Philosophy

1. **Behave like the website, honestly.** Only call routes the official web
   app calls, at a polite rate (hourly polling, at most four concurrent
   requests), with a user agent that names this project. Never impersonate a
   browser and never try to get around Rouvy's bot protection.
2. **Fail loudly and specifically.** A wrong password, a disabled account, a
   firewall block, rate limiting, a session that never starts, and a Rouvy
   outage are different problems with different fixes. Each gets its own error
   type, its own UI message, and its own test.
3. **Degrade gracefully.** The profile is required; every other section is
   optional. A failing section keeps its last good value or becomes
   unavailable on its own, without taking the other sensors down.
4. **Detect upstream change before users do.** Rouvy changes its site without
   notice (the v1 login broke that way). Daily contract canaries exercise the
   login and data routes without an account and open an issue when they fail.
5. **Protect personal data.** Passwords are never logged, never echoed in
   errors (Rouvy's login error response echoes the password back), and
   diagnostics and committed test fixtures are redacted.
6. **One library, three front ends.** A typed async library (`rouvy_api`) does
   all HTTP, decoding, and parsing. The Home Assistant integration and the
   `rouvy-api` CLI are thin layers over it.

## Goals

| Goal | How it is met |
| --- | --- |
| Reliable login | Form login to `login.data`, Firebase error mapping, session verification, transparent re-login with a lock so concurrent requests log in once |
| Useful sensors | ~40 sensors: profile, current week, month and year totals, last activity, challenges, events, routes, career, friends, zones, connected apps |
| Settings from automations | 12 update actions and 6 query actions with response data |
| Simple setup | Config flow with specific errors, reauthentication, and reconfiguration |
| Upgrade safety | Entity unique ids and action names are unchanged from v1 |
| Maintainability | Strict typing, complexity limits, ≥95% branch coverage, documented decisions |

## Non-goals

- Writing to Rouvy on a schedule or without an explicit action call.
- Social-sign-in-only accounts (Google, Apple, Facebook) — the rider must set
  a Rouvy password first.
- Multiple Rouvy accounts per Home Assistant instance.
- Live ride telemetry (power, cadence) — Rouvy does not expose it on the web.

## Functionality

### Sensors

Profile (weight, height, effective FTP, max heart rate, FTP source, units,
name, country); current-week totals across all activity types (distance,
elevation, calories, ride time, activity count, training score);
month-to-date and year-to-date totals; last activity (title, distance,
duration, start time); active and completed challenges; upcoming events and
the next event; favorite routes and riders online on them; career level, XP,
achievements, trophies; friends and friends online; power and heart-rate zones
and connected apps (diagnostic).

### Actions

Updates: `update_weight`, `update_height`, `update_units`, `update_settings`,
`update_profile`, `update_timezone`, `update_ftp`, `update_zones`,
`update_max_heart_rate`, `register_challenge`, `register_event`,
`unregister_event`. Queries (return data): `get_profile`, `get_events`,
`get_challenges`, `get_routes`, `get_activities`, `get_career`.

### CLI

`rouvy-api` mirrors the library for scripting and debugging: `login-check`,
every read, every write, and `raw <route>.data` to inspect decoded payloads.
