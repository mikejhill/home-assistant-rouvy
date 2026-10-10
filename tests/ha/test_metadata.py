"""UX consistency checks: translations, action descriptions, icons, and versions agree."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from custom_components.rouvy.config_flow import _ERROR_KEYS
from custom_components.rouvy.sensor import SENSORS
from custom_components.rouvy.services import QUERY_SERVICES, UPDATE_SERVICES
from rouvy_api import __version__

ROOT: Final = Path(__file__).resolve().parents[2]
INTEGRATION: Final = ROOT / "custom_components" / "rouvy"
type Json = dict[str, "Json"] | list["Json"] | str | int | float | bool | None


class MetadataFiles:
    """Load integration metadata files once per test."""

    @staticmethod
    def json(name: str) -> dict[str, Json]:
        """Return a JSON file from the integration directory."""
        # json.loads returns JSON values, which Json models exactly
        data = cast("Json", json.loads((INTEGRATION / name).read_text(encoding="utf-8")))
        assert isinstance(data, dict)
        return data

    @staticmethod
    def services_yaml() -> dict[str, dict[str, Json] | None]:
        """Return services.yaml."""
        # services.yaml maps action names to optional definitions
        data = cast(
            "dict[str, dict[str, Json] | None]",
            yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8")),
        )
        assert isinstance(data, dict)
        return data

    @staticmethod
    def section(data: dict[str, Json], *path: str) -> dict[str, Json]:
        """Return a nested object."""
        node: Json = data
        for key in path:
            assert isinstance(node, dict), path
            node = node[key]
        assert isinstance(node, dict), path
        return node


@pytest.fixture
def strings() -> dict[str, Json]:
    """strings.json."""
    return MetadataFiles.json("strings.json")


class TestTranslations:
    """Every user-visible key has English text."""

    def test_english_translation_matches_strings(self, strings: dict[str, Json]) -> None:
        """translations/en.json is identical to strings.json."""
        assert MetadataFiles.json("translations/en.json") == strings

    def test_every_sensor_is_named(self, strings: dict[str, Json]) -> None:
        """Every sensor description has a translated name and no orphan names exist."""
        names = MetadataFiles.section(strings, "entity", "sensor")

        assert set(names) == {d.translation_key for d in SENSORS}

    def test_enum_sensor_states_are_translated(self, strings: dict[str, Json]) -> None:
        """Every option of an enum sensor has translated state text."""
        names = MetadataFiles.section(strings, "entity", "sensor")
        for description in SENSORS:
            if description.options is None:
                continue
            states = MetadataFiles.section(names, str(description.translation_key), "state")
            assert set(states) == set(description.options)

    def test_every_config_flow_error_is_translated(self, strings: dict[str, Json]) -> None:
        """Every error the config flow can show has text."""
        errors = MetadataFiles.section(strings, "config", "error")

        assert {key for _, key in _ERROR_KEYS} | {"unknown"} <= set(errors)

    def test_every_exception_key_used_in_code_is_translated(self, strings: dict[str, Json]) -> None:
        """Every translation_key raised by the integration exists under exceptions."""
        used = {
            match
            for path in INTEGRATION.glob("*.py")
            if path.name != "sensor.py"
            for match in re.findall(r'translation_key="(\w+)"', path.read_text(encoding="utf-8"))
        }

        assert used
        assert used <= set(MetadataFiles.section(strings, "exceptions"))

    def test_keys_follow_hassfest_rules(self, strings: dict[str, Json]) -> None:
        """Every translation key is lowercase snake case, as hassfest requires."""
        bad: list[str] = []
        stack: list[tuple[str, Json]] = [("", strings)]
        while stack:
            path, node = stack.pop()
            if not isinstance(node, dict):
                continue
            for key, value in node.items():
                if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*[a-z0-9]|[a-z0-9]", key):
                    bad.append(f"{path}.{key}")
                stack.append((f"{path}.{key}", value))

        assert bad == []

    def test_messages_are_sentences(self, strings: dict[str, Json]) -> None:
        """Errors and descriptions start with a capital letter and end with punctuation."""
        texts = list(MetadataFiles.section(strings, "config", "error").values())
        texts += [
            v["description"]
            for v in MetadataFiles.section(strings, "services").values()
            if isinstance(v, dict)
        ]
        for text in texts:
            assert isinstance(text, str)
            assert text[0].isupper(), text
            assert text.endswith("."), text


class TestActions:
    """services.yaml, strings, icons, and the registered handlers agree."""

    def test_services_yaml_matches_handlers(self) -> None:
        """Every registered action is described in services.yaml and vice versa."""
        assert set(MetadataFiles.services_yaml()) == set(UPDATE_SERVICES) | set(QUERY_SERVICES)

    def test_every_action_and_field_is_translated(self, strings: dict[str, Json]) -> None:
        """Every action and every field has a name and description."""
        services = MetadataFiles.section(strings, "services")
        for name, definition in MetadataFiles.services_yaml().items():
            text = MetadataFiles.section(services, name)
            assert isinstance(text["name"], str)
            assert isinstance(text["description"], str)
            fields = (definition or {}).get("fields") or {}
            assert isinstance(fields, dict)
            for field in fields:
                field_text = MetadataFiles.section(text, "fields", field)
                assert isinstance(field_text["name"], str)
                assert isinstance(field_text["description"], str)

    def test_every_action_and_sensor_has_an_icon(self) -> None:
        """icons.json covers every action and every sensor."""
        icons = MetadataFiles.json("icons.json")
        sensor_icons = MetadataFiles.section(icons, "entity", "sensor")
        service_icons = MetadataFiles.section(icons, "services")

        assert set(service_icons) == set(UPDATE_SERVICES) | set(QUERY_SERVICES)
        unitless = {d.key for d in SENSORS if d.device_class is None or d.key == "ftp"}
        assert unitless - {"weight", "height"} <= set(sensor_icons)


class TestPackaging:
    """Versions and HACS metadata."""

    def test_versions_agree(self) -> None:
        """pyproject, the library, and the integration manifest share one version."""
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        manifest = MetadataFiles.json("manifest.json")

        assert pyproject["project"]["version"] == __version__ == manifest["version"]

    def test_manifest_requirements_empty(self) -> None:
        """The integration ships its own client, so it installs nothing from PyPI."""
        assert MetadataFiles.json("manifest.json")["requirements"] == []

    def test_hacs_metadata(self) -> None:
        """hacs.json names the integration and pins a minimum Home Assistant version."""
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

        assert hacs["name"] == "Rouvy"
        assert re.fullmatch(r"\d{4}\.\d+\.\d+", hacs["homeassistant"])
