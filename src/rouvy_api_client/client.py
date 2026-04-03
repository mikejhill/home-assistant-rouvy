"""HTTP client for the Rouvy API with authentication and typed accessors."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import requests

from .config import RouvyConfig
from .errors import ApiResponseError, AuthenticationError

if TYPE_CHECKING:
    from .models import ActivitySummary, ConnectedApp, TrainingZones, UserProfile

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://riders.rouvy.com"


class RouvyClient:
    """Synchronous HTTP client for the Rouvy indoor cycling API.

    Handles session-based authentication, automatic re-auth on 401,
    and provides typed accessor methods for profile, zones, apps, and
    activity data.
    """

    def __init__(self, config: RouvyConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._authenticated = False

    def login(self) -> None:
        """Authenticate with Rouvy and establish a session."""
        LOGGER.debug("Starting authentication process")
        payload = {"email": self._config.email, "password": self._config.password}
        response = self._session.post(
            f"{BASE_URL}/login.data",
            data=payload,
            timeout=self._config.timeout_seconds,
        )
        if response.status_code >= 400:
            LOGGER.error(
                "Authentication failed",
                extra={"status_code": response.status_code},
            )
            raise AuthenticationError(f"Login failed with status {response.status_code}")

        LOGGER.debug(
            "Login request successful",
            extra={"status_code": response.status_code},
        )

        # Set session cookie by loading _root.data
        LOGGER.debug("Initializing session with _root.data")
        root_response = self._session.get(
            f"{BASE_URL}/_root.data",
            timeout=self._config.timeout_seconds,
        )
        if root_response.status_code >= 400:
            LOGGER.error(
                "Failed to set session cookie",
                extra={"status_code": root_response.status_code},
            )
            raise AuthenticationError(
                f"Session initialization failed with status {root_response.status_code}"
            )

        LOGGER.debug(
            "Session initialized successfully",
            extra={"status_code": root_response.status_code},
        )
        LOGGER.info("Authentication successful")
        self._authenticated = True

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request to the Rouvy API with automatic re-auth.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path or full URL.
            **kwargs: Additional arguments passed to ``requests.Session.request``.

        Returns:
            Response from the Rouvy API.

        Raises:
            AuthenticationError: If authentication fails.
            ApiResponseError: If the API returns an error status.
        """
        LOGGER.debug(
            "Initiating request",
            extra={"method": method, "path": path},
        )

        if not self._authenticated:
            self.login()

        response = self._send_request(method, path, **kwargs)

        # Handle 401 unauthorized
        if response.status_code == 401:
            self._authenticated = False
            LOGGER.debug("Re-authenticating due to 401 response")
            self.login()
            response = self._send_request(method, path, **kwargs)

        # Handle 202 incomplete authentication (session not fully initialized)
        if response.status_code == 202 and self._is_redirect_response(response):
            LOGGER.debug("Incomplete authentication detected, loading _root.data")
            root_response = self._session.get(
                f"{BASE_URL}/_root.data",
                timeout=self._config.timeout_seconds,
            )
            if root_response.status_code >= 400:
                LOGGER.error(
                    "Failed to complete session initialization",
                    extra={"status_code": root_response.status_code},
                )
                raise ApiResponseError(
                    "Session initialization failed",
                    root_response.status_code,
                    _safe_payload(root_response),
                )

            # Retry the original request once
            LOGGER.debug("Retrying request after session initialization")
            response = self._send_request(method, path, **kwargs)
            if response.status_code == 202 and self._is_redirect_response(response):
                LOGGER.error(
                    "Request failed after session initialization retry",
                    extra={"method": method, "url": self._build_url(path)},
                )
                raise ApiResponseError(
                    "Request failed in unknown authentication state",
                    response.status_code,
                    _safe_payload(response),
                )

        if response.status_code >= 400:
            LOGGER.error(
                "Request failed",
                extra={
                    "method": method,
                    "url": self._build_url(path),
                    "status_code": response.status_code,
                },
            )
            raise ApiResponseError(
                "Request failed",
                response.status_code,
                _safe_payload(response),
            )

        LOGGER.info(
            "Request completed successfully",
            extra={"method": method, "status_code": response.status_code},
        )
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Send a GET request to the Rouvy API."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        """Send a POST request to the Rouvy API."""
        return self.request("POST", path, **kwargs)

    def get_user_settings(self) -> requests.Response:
        """Fetch raw user settings response from the API."""
        LOGGER.debug("Fetching user settings")
        return self.get(f"{BASE_URL}/user-settings.data")

    def update_user_settings(self, updates: dict[str, Any]) -> requests.Response:
        """Update user settings with the provided values.

        Args:
            updates: Dictionary of setting names to new values (e.g., {"weight": 86})

        Returns:
            Response from the update request

        Note:
            The API requires height, weight, units, and intent parameters.
            Current values are fetched if not provided in updates.
        """
        from .parser import extract_user_profile

        LOGGER.debug("Updating user settings", extra={"updates": updates})

        # Get current settings to fill in required fields
        current_response = self.get_user_settings()
        current_settings = extract_user_profile(current_response.text)

        # Build the payload with current values as defaults
        # Map from extracted profile keys to API parameter names
        payload = {
            "height": current_settings.get("height_cm", current_settings.get("height", 170)),
            "weight": current_settings.get("weight_kg", current_settings.get("weight", 70)),
            "units": current_settings.get("units", "METRIC"),
            "intent": "update-units",  # Default intent for user settings updates
        }

        # Merge updates into payload
        payload.update(updates)

        LOGGER.info("Posting user settings update", extra={"payload": payload})

        # POST to user-settings.data?index
        response = self.post(
            "user-settings.data?index",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )

        LOGGER.info(
            "User settings updated successfully",
            extra={"status_code": response.status_code},
        )

        return response

    def get_user_profile(self) -> UserProfile:
        """Fetch and return a typed UserProfile model."""
        from .parser import extract_user_profile_model

        response = self.get_user_settings()
        return extract_user_profile_model(response.text)

    def get_training_zones(self) -> TrainingZones:
        """Fetch and return typed TrainingZones from the zones endpoint."""
        from .parser import extract_training_zones_model

        LOGGER.debug("Fetching training zones")
        response = self.get(f"{BASE_URL}/user-settings/zones.data")
        return extract_training_zones_model(response.text)

    def get_connected_apps(self) -> list[ConnectedApp]:
        """Fetch and return a list of typed ConnectedApp models."""
        from .parser import extract_connected_apps_model

        LOGGER.debug("Fetching connected apps")
        response = self.get(f"{BASE_URL}/user-settings/connected-apps.data")
        return extract_connected_apps_model(response.text)

    def get_activity_summary(self) -> ActivitySummary:
        """Fetch and return a typed ActivitySummary from the profile overview."""
        from .parser import extract_activities_model

        LOGGER.debug("Fetching activity summary")
        response = self.get(f"{BASE_URL}/profile/overview.data")
        return extract_activities_model(response.text)

    def _send_request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self._config.timeout_seconds

        url = self._build_url(path)
        start_time = time.perf_counter()
        response = self._session.request(method, url, **kwargs)
        duration_ms = (time.perf_counter() - start_time) * 1000

        LOGGER.debug(
            "HTTP request completed",
            extra={
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path

        return f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"

    def _is_redirect_response(self, response: requests.Response) -> bool:
        """Check if response is a SingleFetchRedirect indicating incomplete auth."""
        try:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return bool(data[0] == ["SingleFetchRedirect", 1])
            return False
        except (ValueError, TypeError, IndexError):
            return False


def _safe_payload(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
