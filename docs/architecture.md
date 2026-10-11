# Architecture

```text
src/rouvy_api/                 Async library (source of truth, no Home Assistant imports)
├── turbo_stream.py            Spec-correct turbo-stream v2 decoder (promises, dates, sentinels, cycles)
├── payload.py                 Payload (breadth-first key search, redirects) and Fields (typed accessors)
├── parsers.py                 Payload -> frozen dataclass models, located by key name, not route id
├── models.py                  Immutable models with as_json()
├── auth.py                    HTTP status classification and login-response interpretation
├── client.py                  RouvyClient: login, session verification, re-auth lock, reads, writes
├── config.py                  ClientConfig, Credentials, Endpoint paths, User-Agent
└── cli/                       rouvy-api command-line interface

custom_components/rouvy/       Home Assistant integration (HACS installs only this folder)
├── rouvy_api/                 Generated copy of src/rouvy_api (without cli/); never edit by hand
├── api.py                     RouvyClientFactory: client + dedicated aiohttp session
├── coordinator.py             Polls hourly: profile (required) + 9 optional sections concurrently
├── sensor.py                  Sensor descriptions computed from an immutable RouvySnapshot
├── services.py                Update and query actions with probatio schemas
├── config_flow.py             User, reauth, and reconfigure steps
└── diagnostics.py             Redacted snapshot export
```

## Request flow

1. `RouvyClient._request` takes the auth lock only to check or establish the
   session, then sends requests concurrently.
2. Login posts `email`/`password` to `login.data`. A rejected login is HTTP 200
   with a form error carrying a Firebase code; `LoginResponseInterpreter` maps
   the code to an exception. A success is then verified by reading
   `user-settings.data`: a sign-in redirect there means no session was created
   (`RouvySessionError`).
3. A 401 or a redirect to `account.rouvy.com/sign-in` on a later read marks
   the session generation stale; the first request to notice logs in again and
   the others reuse the new session. A second failure raises `RouvySessionError`.
4. Responses are decoded by `TurboStreamDecoder` and parsed by `RouvyParser`.

## Endpoints

| Data | Route | Notes |
| --- | --- | --- |
| Login | `login.data` (POST) | Form login; failures are HTTP 200 form errors |
| Profile | `user-settings.data` | Also verifies the session after login |
| Profile, units, privacy writes | `user-settings.data?index` (POST) | Intents `update-profile` (incl. timezone, language), `update-units`, `update-social` |
| Zones and FTP | `user-settings/zones.data` (GET/POST) | |
| Connected apps | `user-settings/connected-apps.data` | |
| Activities, totals, career, friends | `profile/overview.data` | Deferred promises carry statistics and career |
| Weekly stats | `resources/activity-stats.data` (POST) | Week bounds in display format, end exclusive |
| Challenges | `challenges/status/available.data` | |
| Favorite routes | `routes/collection/favourite.data` | |
| Events | `events.data` | Joined, upcoming, and featured lists |
| Achievements, trophies | `profile/achievements.data`, `profile/trophies.data` | |

## Why the v1 login broke (October 2026)

- Rouvy's Cloudflare firewall started rejecting generic library user agents
  (`python-requests`, `aiohttp`, `HomeAssistant/… aiohttp/…`) with HTTP 403.
- The `/_root.data` route the v1 client called after login was removed (404),
  so every login failed.
- v1 treated any HTTP status below 400 as a successful login, but Rouvy
  reports wrong passwords as HTTP 200 form errors, so bad credentials looked
  like a mystery session failure.

v2 sends a project-identifying user agent, drops `/_root.data`, verifies the
session explicitly, and maps login errors precisely. The daily contract canary
(`tests/contract`) covers all three behaviours without an account.

## Decisions

See [ADR 0001](adr/0001-vendored-library.md) and [ADR 0002](adr/0002-login-and-session-handling.md).
