# ADR 0002: Login and session handling

- Status: accepted
- Date: 2026-10-10

## Context

Rouvy moved interactive sign-in to an email-first flow on `account.rouvy.com`
(client-side Firebase, then `resources/auth`). The riders portal still accepts
a server-side form login at `login.data`, which validates the password with
Firebase and returns a form error on failure. Cloudflare in front of the
riders portal rejects generic HTTP library user agents.

## Decision

- Keep the riders-portal form login: it is one request, needs no Firebase
  client, and is what the riders web app's own route serves.
- Identify the client as `home-assistant-rouvy/<version> (+repo URL)`. Do not
  spoof a browser.
- Verify every login by reading `user-settings.data`; if Rouvy redirects to
  sign-in, raise `RouvySessionError` with a message that points to an upstream
  change, instead of pretending the password is wrong.
- Never log response bodies of the login route (they echo the password).
- Each config entry gets a dedicated aiohttp session (`auto_cleanup=False`,
  detached on unload), because login clears that session's Rouvy cookies.

## Consequences

If Rouvy retires `login.data`, the canary fails and setup reports
`auth_flow_changed`. The fallback would be Firebase REST
`accounts:signInWithPassword` followed by `account.rouvy.com/resources/auth`,
documented here for that day.
