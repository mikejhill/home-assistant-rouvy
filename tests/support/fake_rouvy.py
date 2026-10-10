"""In-process fake of the Rouvy riders portal for end-to-end tests.

It mimics the behaviours the client depends on: firewall rejection of generic user
agents, form-error login failures, cookie sessions, sign-in redirects for anonymous
readers, and action endpoints that record what was submitted.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Final

from aiohttp import web

from rouvy_api.config import Endpoint
from tests.support.rouvy_payloads import RouvyPayloads

SESSION_COOKIE: Final = "rouvy_session"
BLOCKED_AGENT_MARKERS: Final = ("python-requests", "aiohttp", "homeassistant/")
VALID_EMAIL: Final = "rider@example.com"
VALID_PASSWORD: Final = "correct-horse-battery"
TURBO_CONTENT_TYPE: Final = "text/x-script"
FIREWALL_PAGE: Final = "<!DOCTYPE html><html><title>Attention Required! | Cloudflare</title></html>"


@dataclass(slots=True)
class RecordedRequest:
    """One request seen by the fake server."""

    method: str
    path: str
    form: dict[str, str]
    user_agent: str


@dataclass(slots=True)
class FakeRouvyState:
    """Mutable behaviour switches and recordings for FakeRouvy."""

    accounts: dict[str, str] = field(default_factory=lambda: {VALID_EMAIL: VALID_PASSWORD})
    disabled_accounts: set[str] = field(default_factory=set)
    sessions: set[str] = field(default_factory=set)
    bodies: dict[str, str] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0
    issue_session_cookie: bool = True
    requests: list[RecordedRequest] = field(default_factory=list)
    login_count: int = 0

    def expire_sessions(self) -> None:
        """Invalidate every session, as Rouvy does when a session times out."""
        self.sessions.clear()

    def posts_to(self, path: str) -> list[dict[str, str]]:
        """Return the forms POSTed to a path."""
        return [r.form for r in self.requests if r.method == "POST" and r.path == path]


class FakeRouvy:
    """aiohttp application emulating riders.rouvy.com."""

    def __init__(self, payloads: RouvyPayloads | None = None) -> None:
        self._payloads = payloads or RouvyPayloads()
        self.state = FakeRouvyState(bodies=self._payloads.all_reads())

    def build_app(self) -> web.Application:
        """Return the aiohttp application."""
        app = web.Application()
        app.router.add_post(f"/{Endpoint.LOGIN}", self._login)
        app.router.add_route("*", "/{path:.+}", self._data)
        return app

    # Handlers

    async def _guard(self, request: web.Request) -> web.Response | None:
        """Record the request, apply latency, and reject blocked user agents."""
        agent = request.headers.get("User-Agent", "")
        form = {k: str(v) for k, v in (await request.post()).items()}
        path = request.path_qs.lstrip("/")
        self.state.requests.append(RecordedRequest(request.method, path, form, agent))
        if self.state.latency_s:
            await asyncio.sleep(self.state.latency_s)
        if any(marker in agent.lower() for marker in BLOCKED_AGENT_MARKERS):
            return web.Response(status=403, text=FIREWALL_PAGE, content_type="text/html")
        return None

    async def _login(self, request: web.Request) -> web.Response:
        """Authenticate a form login."""
        if (blocked := await self._guard(request)) is not None:
            return blocked
        self.state.login_count += 1
        form = await request.post()
        email, password = str(form.get("email", "")), str(form.get("password", ""))
        if self.state.accounts.get(email) != password:
            body = self._payloads.login_error(
                "Firebase: Error (auth/invalid-credential).", email, password
            )
            return self._turbo(body)
        if email in self.state.disabled_accounts:
            body = self._payloads.login_error("Firebase: Error (auth/user-disabled).", email, "")
            return self._turbo(body)
        response = self._turbo(self._payloads.redirect("/"), status=202)
        if self.state.issue_session_cookie:
            token = secrets.token_hex(16)
            self.state.sessions.add(token)
            response.set_cookie(SESSION_COOKIE, token, httponly=True)
        return response

    async def _data(self, request: web.Request) -> web.Response:
        """Serve data routes and accept actions for authenticated sessions."""
        if (blocked := await self._guard(request)) is not None:
            return blocked
        path = request.path_qs.lstrip("/")
        if path in self.state.failures:
            return web.Response(status=self.state.failures[path], text="error")
        if request.cookies.get(SESSION_COOKIE) not in self.state.sessions:
            return self._turbo(self._payloads.sign_in_redirect(path), status=202)
        if request.method == "POST" and path != Endpoint.ACTIVITY_STATS:
            return self._turbo(self._payloads.action_ok())
        body = self.state.bodies.get(path.partition("?")[0])
        if body is None:
            return web.Response(status=404, text="Not Found", content_type=TURBO_CONTENT_TYPE)
        return self._turbo(body)

    @staticmethod
    def _turbo(body: str, status: int = 200) -> web.Response:
        """Return a turbo-stream response."""
        return web.Response(status=status, text=body, content_type=TURBO_CONTENT_TYPE)
