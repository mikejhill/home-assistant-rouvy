"""Tests for redacted diagnostics."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.diagnostics import (
    REDACTED,
    SnapshotExporter,
    async_get_config_entry_diagnostics,
)
from custom_components.rouvy.rouvy_api import JsonValue
from tests.support.fake_rouvy import VALID_EMAIL, VALID_PASSWORD


class TestDiagnostics:
    """Diagnostics content."""

    async def test_contains_data_without_personal_details(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """Diagnostics include the snapshot but never credentials or identity fields."""
        result = await async_get_config_entry_diagnostics(hass, loaded_entry)

        text = json.dumps(result)
        assert VALID_EMAIL not in text
        assert VALID_PASSWORD not in text
        assert "test-rider" not in text
        assert result["last_update_success"] is True
        snapshot = result["snapshot"]
        assert isinstance(snapshot, dict)
        assert isinstance(snapshot["profile"], dict)
        assert snapshot["profile"]["email"] == REDACTED
        assert snapshot["profile"]["weight_kg"] == 85.0

    def test_export_before_first_refresh(self) -> None:
        """No snapshot exports as None."""
        assert SnapshotExporter.export(None) is None

    def test_redact_nested(self) -> None:
        """Redaction applies inside lists and nested objects but keeps None values."""
        tree: JsonValue = {"events": [{"title": "Ride", "capacity": 3}], "team": None}

        assert SnapshotExporter.redact(tree) == {
            "events": [{"title": REDACTED, "capacity": 3}],
            "team": None,
        }
