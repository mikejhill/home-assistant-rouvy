"""Diagnostics for the Rouvy integration, with personal data redacted."""

from __future__ import annotations

from typing import Final

from homeassistant.core import HomeAssistant

from custom_components.rouvy.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.rouvy.coordinator import RouvyConfigEntry, RouvySnapshot
from custom_components.rouvy.rouvy_api import JsonValue

REDACTED: Final = "**REDACTED**"
TO_REDACT: Final = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "user_id",
    "username",
    "first_name",
    "last_name",
    "birth_date",
    "title",
}


class SnapshotExporter:
    """Convert a snapshot into JSON-compatible diagnostics."""

    @staticmethod
    def export(snapshot: RouvySnapshot | None) -> dict[str, JsonValue] | None:
        """Return each snapshot section, or None before the first refresh."""
        if snapshot is None:
            return None
        sections: dict[str, JsonValue] = {
            "fetched_at": snapshot.fetched_at.isoformat(),
            "profile": snapshot.profile.as_json(),
            "zones": snapshot.zones.as_json() if snapshot.zones else None,
            "overview": snapshot.overview.as_json() if snapshot.overview else None,
            "achievements": snapshot.achievements.as_json() if snapshot.achievements else None,
            "trophies": snapshot.trophies.as_json() if snapshot.trophies else None,
        }
        for name in ("connected_apps", "weekly_stats", "challenges", "favorite_routes", "events"):
            items = getattr(snapshot, name)
            sections[name] = [item.as_json() for item in items] if items is not None else None
        return sections

    @staticmethod
    def redact(value: JsonValue) -> JsonValue:
        """Replace values of sensitive keys anywhere in a JSON tree."""
        if isinstance(value, dict):
            return {
                key: REDACTED
                if key in TO_REDACT and item is not None
                else SnapshotExporter.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [SnapshotExporter.redact(item) for item in value]
        return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001 - HA signature
    entry: RouvyConfigEntry,
) -> dict[str, JsonValue]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    report: dict[str, JsonValue] = {
        "entry": {str(key): REDACTED for key in entry.data},
        "last_update_success": coordinator.last_update_success,
        "snapshot": SnapshotExporter.export(coordinator.data),
    }
    return {key: SnapshotExporter.redact(item) for key, item in report.items()}
