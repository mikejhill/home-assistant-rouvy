#!/usr/bin/env python3
"""
AppDaemon integration for the Rouvy API client.

Supports three command interfaces:
1. Pseudo-service via call_service events (recommended) - call rouvy_api.fetch from HASS
2. JSON text helper - write JSON to input_text.appdaemon_app_trigger
3. Traditional sensor state change
"""

from __future__ import annotations

import json
import os
from typing import Any

import appdaemon.plugins.hass.hassapi as hass

from rouvy_api_client import RouvyClient, RouvyConfig

DEFAULT_SENSOR = "sensor.dummy"
DEFAULT_ENDPOINT = "user-settings.data"
DEFAULT_TARGET_SENSOR = "sensor.rouvy_api_status"
DEFAULT_COMMAND_SENSOR = "input_text.appdaemon_app_trigger"
DEFAULT_SERVICE_DOMAIN = "rouvy_api"
DEFAULT_SERVICE_NAME = "fetch"


class RouvyApp(hass.Hass):
    """Listen to a Home Assistant sensor and call the Rouvy API on changes."""

    def initialize(self) -> None:
        # Testing
        if True:
            self.register_service("rouvy_api", "fetch", self._on_service_called)
            a = self.get_entity("sensor.dummy")  # Ensure sensor exists for testing
            a.call_service

        self._app_name = self.name  # AppDaemon app instance name
        self._sensor = str(self.args.get("sensor", DEFAULT_SENSOR))
        self._endpoint = str(self.args.get("endpoint", DEFAULT_ENDPOINT))
        target_sensor = self.args.get("target_sensor", DEFAULT_TARGET_SENSOR)
        self._target_sensor = str(target_sensor) if target_sensor else ""

        command_sensor = self.args.get("command_sensor", DEFAULT_COMMAND_SENSOR)
        self._command_sensor = str(command_sensor) if command_sensor else ""

        # Pseudo-service configuration
        self._service_domain = str(
            self.args.get("service_domain", DEFAULT_SERVICE_DOMAIN)
        )
        self._service_name = str(self.args.get("service_name", DEFAULT_SERVICE_NAME))

        email = self.args.get("email") or os.getenv("ROUVY_EMAIL")
        password = self.args.get("password") or os.getenv("ROUVY_PASSWORD")
        if not email or not password:
            self.error(
                "ROUVY_EMAIL and ROUVY_PASSWORD must be set via app args or environment"
            )
            return

        config = RouvyConfig(email=email, password=password)
        self._client = RouvyClient(config)

        # Method 1: Traditional sensor state change listener
        self.listen_state(self._on_sensor_change, self._sensor)

        # Method 2: JSON command sensor listener (if configured)
        if self._command_sensor:
            self.listen_state(self._on_command_received, self._command_sensor)
            self.log(
                "Listening for JSON commands on %s (app_name=%s)",
                self._command_sensor,
                self._app_name,
            )

        # Method 3: Pseudo-service via call_service event (RECOMMENDED)
        # Listen for service calls to our domain.service
        self.listen_event(
            self._on_service_called,
            event="call_service",
            domain=self._service_domain,
            service=self._service_name,
        )

        self.log(
            "RouvyApp initialized: sensor=%s, endpoint=%s, target_sensor=%s, pseudo-service=%s.%s",
            self._sensor,
            self._endpoint,
            self._target_sensor or "(none)",
            self._service_domain,
            self._service_name,
        )

    def _on_sensor_change(
        self,
        entity: str,
        attribute: str,
        old: Any,
        new: Any,
        kwargs: dict[str, Any],
    ) -> None:
        if old == new:
            return

        self.log("Sensor %s changed from %s to %s", entity, old, new)

        try:
            response = self._client.get(self._endpoint)
        except Exception as exc:  # pragma: no cover - AppDaemon logs exceptions
            self.error("Rouvy API request failed: %s", exc)
            return

        if not self._target_sensor:
            self.log(
                "Rouvy API response %s (%d bytes)",
                response.status_code,
                len(response.text),
            )
            return

        self.set_state(
            self._target_sensor,
            state=str(response.status_code),
            attributes={
                "endpoint": self._endpoint,
                "bytes": len(response.text),
                "source_sensor": entity,
            },
        )

    def _on_command_received(
        self,
        entity: str,
        attribute: str,
        old: Any,
        new: Any,
        kwargs: dict[str, Any],
    ) -> None:
        """Parse JSON command from text helper and execute if app_name matches."""
        if not new or old == new:
            return

        try:
            command = json.loads(str(new))
        except (json.JSONDecodeError, TypeError) as exc:
            self.error("Invalid JSON in command sensor %s: %s", entity, exc)
            return

        if not isinstance(command, dict):
            self.error("Command must be a JSON object, got %s", type(command).__name__)
            return

        target_app = command.get("app_name")
        if target_app != self._app_name:
            self.log(
                "Ignoring command for app_name=%s (this app is %s)",
                target_app,
                self._app_name,
            )
            return

        self.log("Received command: %s", command)
        endpoint = command.get("endpoint", self._endpoint)
        self._fetch_and_store(endpoint, source=f"command:{entity}")

    def _on_service_called(
        self, event_name: str, data: dict[str, Any], kwargs: dict[str, Any]
    ) -> None:
        """Handle call_service events for our pseudo-service.

        Call from HASS:
            service: rouvy_api.fetch
            data:
              endpoint: user-settings.data
        """
        service_data = data.get("service_data", {})
        endpoint = service_data.get("endpoint", self._endpoint)

        self.log(
            "Pseudo-service %s.%s called with endpoint=%s",
            self._service_domain,
            self._service_name,
            endpoint,
        )
        self._fetch_and_store(
            endpoint, source=f"service:{self._service_domain}.{self._service_name}"
        )

    def _fetch_and_store(self, endpoint: str, source: str = "unknown") -> None:
        """Fetch from Rouvy API and optionally store result in target sensor."""
        try:
            response = self._client.get(endpoint)
        except Exception as exc:  # pragma: no cover - AppDaemon logs exceptions
            self.error("Rouvy API request failed (endpoint=%s): %s", endpoint, exc)
            return

        if not self._target_sensor:
            self.log(
                "Rouvy API response %s (%d bytes) [source=%s]",
                response.status_code,
                len(response.text),
                source,
            )
            return

        self.set_state(
            self._target_sensor,
            state=str(response.status_code),
            attributes={
                "endpoint": endpoint,
                "bytes": len(response.text),
                "source": source,
                "app_name": self._app_name,
            },
        )
