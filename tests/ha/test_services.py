"""Tests for the Rouvy actions (services)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rouvy.const import DOMAIN
from custom_components.rouvy.services import QUERY_SERVICES, UPDATE_SERVICES
from rouvy_api.config import Endpoint
from tests.support.fake_rouvy import FakeRouvy
from tests.support.rouvy_payloads import CHALLENGE_SLUG, EVENT_ID

type ServiceData = dict[str, str | int | float | list[int] | dict[str, str | float]]


class TestUpdateServices:
    """Actions that change Rouvy settings."""

    @pytest.mark.parametrize(
        ("service", "data", "path", "expected"),
        [
            pytest.param(
                "update_weight",
                {"weight": 80.5},
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-units", "weight": "80.5", "height": "178.0", "units": "METRIC"},
                id="weight",
            ),
            pytest.param(
                "update_height",
                {"height": 181},
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-units", "weight": "85.0", "height": "181.0"},
                id="height",
            ),
            pytest.param(
                "update_units",
                {"units": "imperial"},
                Endpoint.USER_SETTINGS_ACTION,
                {"units": "IMPERIAL"},
                id="units",
            ),
            pytest.param(
                "update_settings",
                {"settings": {"weight": 70, "units": "METRIC"}},
                Endpoint.USER_SETTINGS_ACTION,
                {"weight": "70.0", "units": "METRIC"},
                id="settings",
            ),
            pytest.param(
                "update_profile",
                {"firstName": "Ada", "userName": "ada_rides"},
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-profile", "firstName": "Ada", "username": "ada_rides"},
                id="profile",
            ),
            pytest.param(
                "update_profile",
                {"accountPrivacy": "private"},
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-social", "privacy": "PRIVATE"},
                id="privacy",
            ),
            pytest.param(
                "update_timezone",
                {"timezone": "Europe/Prague"},
                Endpoint.USER_SETTINGS_ACTION,
                {"intent": "update-profile", "timezone": "Europe/Prague", "language": "en"},
                id="timezone",
            ),
            pytest.param(
                "update_ftp",
                {"ftp_source": "MANUAL", "value": 250},
                Endpoint.ZONES,
                {"type": "power", "ftpSource": "MANUAL", "value": "250"},
                id="ftp",
            ),
            pytest.param(
                "update_zones",
                {"zone_type": "heartRate", "zones": [60, 66, 76, 83, 90, 95]},
                Endpoint.ZONES,
                {"type": "heartRate", "zones": "[60,66,76,83,90,95]", "value": "190"},
                id="zones",
            ),
            pytest.param(
                "update_max_heart_rate",
                {"max_heart_rate": 186},
                Endpoint.ZONES,
                {"type": "heartRate", "oldValue": "190", "value": "186"},
                id="max-hr",
            ),
            pytest.param(
                "register_challenge",
                {"slug": CHALLENGE_SLUG},
                f"challenges/{CHALLENGE_SLUG}.data",
                {"intent": "register"},
                id="challenge",
            ),
            pytest.param(
                "register_event",
                {"event_id": EVENT_ID},
                f"events/{EVENT_ID}.data",
                {"intent": "register", "eventId": EVENT_ID},
                id="register-event",
            ),
            pytest.param(
                "unregister_event",
                {"event_id": EVENT_ID},
                f"events/{EVENT_ID}.data",
                {"intent": "unregister"},
                id="unregister-event",
            ),
        ],
    )
    async def test_posts_expected_form(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        fake_rouvy: FakeRouvy,
        service: str,
        data: ServiceData,
        path: str,
        expected: dict[str, str],
    ) -> None:
        """Each action submits the form Rouvy's web app would submit, then refreshes."""
        reads_before = len(fake_rouvy.state.requests)

        await hass.services.async_call(DOMAIN, service, data, blocking=True)
        await hass.async_block_till_done()

        forms = fake_rouvy.state.posts_to(path)
        assert forms, f"no POST to {path}"
        assert expected.items() <= forms[-1].items()
        assert len(fake_rouvy.state.requests) > reads_before + 1

    @pytest.mark.parametrize(
        ("service", "data"),
        [
            pytest.param("update_weight", {"weight": 5}, id="weight-too-low"),
            pytest.param("update_units", {"units": "STONE"}, id="bad-units"),
            pytest.param("update_ftp", {"ftp_source": "GUESS"}, id="bad-ftp-source"),
            pytest.param("register_event", {"event_id": "../admin"}, id="path-injection"),
            pytest.param("update_settings", {"settings": {}}, id="empty-settings"),
        ],
    )
    async def test_schema_rejects_bad_input(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, service: str, data: ServiceData
    ) -> None:
        """Invalid input is rejected by the schema before reaching Rouvy."""
        with pytest.raises(Exception, match=r"\S"):
            await hass.services.async_call(DOMAIN, service, data, blocking=True)

    async def test_library_validation_becomes_service_validation_error(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """Non-increasing zones raise a translated ServiceValidationError."""
        with pytest.raises(ServiceValidationError) as excinfo:
            await hass.services.async_call(
                DOMAIN, "update_zones", {"zone_type": "power", "zones": [60, 50]}, blocking=True
            )

        assert excinfo.value.translation_key == "invalid_request"

    async def test_manual_ftp_without_value(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """MANUAL FTP without a value is a validation error."""
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "update_ftp", {"ftp_source": "MANUAL"}, blocking=True
            )

    async def test_empty_profile_update(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """update_profile with no fields asks the user to provide one."""
        with pytest.raises(ServiceValidationError) as excinfo:
            await hass.services.async_call(DOMAIN, "update_profile", {}, blocking=True)

        assert excinfo.value.translation_key == "profile_update_empty"

    async def test_rouvy_failure_becomes_home_assistant_error(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_rouvy: FakeRouvy
    ) -> None:
        """A Rouvy server error surfaces as a translated HomeAssistantError."""
        fake_rouvy.state.failures[Endpoint.USER_SETTINGS_ACTION] = 500

        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call(
                DOMAIN, "update_timezone", {"timezone": "Europe/Prague"}, blocking=True
            )

        assert excinfo.value.translation_key == "request_failed"


class TestQueryServices:
    """Actions that return data."""

    @pytest.mark.parametrize(
        ("service", "key", "size"),
        [
            ("get_events", "events", 2),
            ("get_challenges", "challenges", 3),
            ("get_routes", "routes", 2),
            ("get_activities", "activities", 10),
        ],
    )
    async def test_list_queries(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, service: str, key: str, size: int
    ) -> None:
        """List queries return JSON lists of the expected size."""
        response = await hass.services.async_call(
            DOMAIN, service, {}, blocking=True, return_response=True
        )

        assert response is not None
        items = response[key]
        assert isinstance(items, list)
        assert len(items) == size

    async def test_profile_and_career(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """Profile and career queries return JSON objects."""
        profile = await hass.services.async_call(
            DOMAIN, "get_profile", {}, blocking=True, return_response=True
        )
        career = await hass.services.async_call(
            DOMAIN, "get_career", {}, blocking=True, return_response=True
        )

        assert profile is not None
        assert career is not None
        profile_data = profile["profile"]
        career_data = career["career"]
        assert isinstance(profile_data, dict)
        assert isinstance(career_data, dict)
        assert profile_data["email"] == "rider@example.com"
        assert career_data["level"] == 5


class TestServiceRegistration:
    """Registration and routing."""

    async def test_all_services_registered(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """Every action is registered under the rouvy domain."""
        registered = set(hass.services.async_services_for_domain(DOMAIN))

        assert registered == set(UPDATE_SERVICES) | set(QUERY_SERVICES)

    async def test_call_without_loaded_entry(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ) -> None:
        """Calling an action while the entry is unloaded explains what is wrong."""
        await hass.config_entries.async_unload(loaded_entry.entry_id)

        with pytest.raises(ServiceValidationError) as excinfo:
            await hass.services.async_call(
                DOMAIN, "get_profile", {}, blocking=True, return_response=True
            )

        assert excinfo.value.translation_key == "not_loaded"
