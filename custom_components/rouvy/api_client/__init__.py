"""Rouvy API client library for authentication, session management, and data parsing."""

from __future__ import annotations

from .client import RouvyClient
from .config import RouvyConfig
from .errors import ApiResponseError, AuthenticationError, RouvyApiError
from .models import (
    Activity,
    ActivitySummary,
    ConnectedApp,
    TrainingZones,
    UserProfile,
)
from .parser import (
    TurboStreamDecoder,
    extract_activities_model,
    extract_connected_apps_model,
    extract_training_zones_model,
    extract_user_profile,
    extract_user_profile_model,
    parse_response,
)

__all__ = [
    "Activity",
    "ActivitySummary",
    "ApiResponseError",
    "AuthenticationError",
    "ConnectedApp",
    "RouvyApiError",
    "RouvyClient",
    "RouvyConfig",
    "TrainingZones",
    "TurboStreamDecoder",
    "UserProfile",
    "extract_activities_model",
    "extract_connected_apps_model",
    "extract_training_zones_model",
    "extract_user_profile",
    "extract_user_profile_model",
    "parse_response",
]
