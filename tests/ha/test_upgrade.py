"""Upgrading from v1 must not raise long-term statistics repairs."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    async_import_statistics,
    validate_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

V1_STATISTICS: Final = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v1-sensor-statistics.json"
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_mock: Recorder,  # requested first: the recorder must start before hass
    enable_custom_integrations: None,
) -> None:
    """Start the recorder, then load custom_components/rouvy."""


class V1Statistics:
    """Seed the recorder with the statistics metadata a v1 install accumulated."""

    def __init__(self, hass: HomeAssistant, entry: MockConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._registry = er.async_get(hass)

    @staticmethod
    def baseline() -> dict[str, dict[str, str | None]]:
        """Return sensor key -> v1 state class and unit."""
        data = json.loads(V1_STATISTICS.read_text(encoding="utf-8"))
        return {key: value for key, value in data.items() if not key.startswith("_")}

    def entity_id(self, key: str) -> str:
        """Return the entity id for a sensor key (unique ids are stable across versions)."""
        entity_id = self._registry.async_get_entity_id(
            "sensor", "rouvy", f"{self._entry.entry_id}_{key}"
        )
        assert entity_id is not None, f"v1 sensor {key!r} no longer exists"
        return entity_id

    async def enable_all(self) -> None:
        """Enable sensors that start disabled; v1 users may have them enabled."""
        for entry in er.async_entries_for_config_entry(self._registry, self._entry.entry_id):
            if entry.disabled_by is not None:
                self._registry.async_update_entity(entry.entity_id, disabled_by=None)
        assert await self._hass.config_entries.async_reload(self._entry.entry_id)
        await self._hass.async_block_till_done()

    def seed(self) -> None:
        """Import one hour of statistics per v1 sensor with v1's metadata."""
        start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
        for key, v1 in self.baseline().items():
            unit = v1["unit"]
            converter = STATISTIC_UNIT_TO_UNIT_CONVERTER.get(unit)
            is_total = v1["state_class"] != "measurement"
            metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE if is_total else StatisticMeanType.ARITHMETIC,
                has_sum=is_total,
                name=None,
                source="recorder",
                statistic_id=self.entity_id(key),
                unit_class=converter.UNIT_CLASS if converter else None,
                unit_of_measurement=unit,
            )
            row = (
                StatisticData(start=start, sum=1.0, state=1.0)
                if is_total
                else StatisticData(start=start, mean=1.0, min=1.0, max=1.0)
            )
            async_import_statistics(self._hass, metadata, [row])


class TestUpgradeFromV1:
    """v2 keeps every statistic v1 recorded valid."""

    async def test_no_statistics_issues(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """No state class removals, unit changes, or mean type changes against v1 metadata."""
        v1 = V1Statistics(hass, loaded_entry)
        await v1.enable_all()
        v1.seed()
        await async_wait_recording_done(hass)

        issues = await get_instance(hass).async_add_executor_job(validate_statistics, hass)

        rouvy = {v1.entity_id(key) for key in v1.baseline()}
        assert {k: v for k, v in issues.items() if k in rouvy} == {}
