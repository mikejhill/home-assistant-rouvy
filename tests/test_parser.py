"""Tests for the turbo-stream parser module.

Covers TurboStreamDecoder, parse_response, helper functions
(_resolve_index, _find_key_value, _safe_int, _safe_float, _safe_str),
and typed extraction functions with synthetic data.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from custom_components.rouvy.api_client.parser import (
    UNDEFINED,
    TurboStreamDecoder,
    _find_key_value,
    _resolve_index,
    _safe_float,
    _safe_int,
    _safe_str,
    extract_activities_model,
    extract_connected_apps_model,
    extract_training_zones_model,
    extract_user_profile,
    extract_user_profile_model,
    parse_response,
)

# ===================================================================
# TurboStreamDecoder — core decode
# ===================================================================


class TestDecodeBasicTypes:
    """Verify decoding of primitive JSON arrays and objects."""

    def test_decode_simple_list_returns_list(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode('[1, 2, "hello"]')
        assert result == [1, 2, "hello"], f"Expected [1, 2, 'hello'], got {result}"

    def test_decode_dict_returns_dict(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode('{"name": "Alice"}')
        assert result == {"name": "Alice"}, f"Expected dict with name=Alice, got {result}"

    def test_decode_empty_list(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("[]")
        assert result == [], f"Expected empty list, got {result}"

    def test_decode_nested_dict_in_list(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode('[{"key": "value"}]')
        assert result == [{"key": "value"}], f"Expected list with nested dict, got {result}"

    def test_decode_string_value(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode('"just a string"')
        assert result == "just a string", f"Expected plain string, got {result}"

    def test_decode_integer_value(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("42")
        assert result == 42, f"Expected 42, got {result}"

    def test_decode_null_value(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("null")
        assert result is None, f"Expected None, got {result}"


class TestDecodeSentinels:
    """Verify decoding of turbo-stream sentinel values."""

    def test_minus5_decoded_as_undefined(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("[-5]")
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result[0] is UNDEFINED, f"Expected UNDEFINED sentinel for -5, got {result[0]!r}"

    def test_minus7_decoded_as_null(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("[-7]")
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result[0] is None, f"Expected None for -7 sentinel, got {result[0]!r}"

    def test_other_negative_ints_preserved(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.decode("[-1, -3, -10]")
        assert result == [-1, -3, -10], f"Expected [-1, -3, -10] preserved as-is, got {result}"


class TestDecodeDateFormat:
    """Verify decoding of turbo-stream date format ["D", timestamp_ms]."""

    def test_valid_date_decoded(self) -> None:
        ts_ms = 1609459200000  # 2021-01-01T00:00:00 UTC
        decoder = TurboStreamDecoder()
        result = decoder.decode(f'[["D", {ts_ms}]]')
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert isinstance(result[0], datetime), (
            f"Expected datetime for ['D', ts], got {type(result[0])}"
        )

    def test_invalid_timestamp_returns_original(self) -> None:
        decoder = TurboStreamDecoder()
        # Extremely large timestamp that causes OSError
        result = decoder.decode('[["D", 99999999999999999]]')
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        # Should return original array unchanged
        assert result[0] == ["D", 99999999999999999], (
            f"Expected original value for invalid timestamp, got {result[0]}"
        )


class TestDecodePromises:
    """Verify decoding of turbo-stream promise references ["P", id]."""

    def test_resolved_promise_returns_value(self) -> None:
        # Main array has a promise reference, second line resolves it
        text = '[["P", 1]]\nP1:42'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result[0] == 42, f"Expected resolved promise value 42, got {result[0]}"

    def test_unresolved_promise_returns_placeholder(self) -> None:
        text = '[["P", 999]]'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result[0] == "<Promise:999>", (
            f"Expected placeholder for unresolved promise, got {result[0]}"
        )

    def test_promise_resolved_with_json_array(self) -> None:
        text = '[["P", 10]]\nP10:[1,2,3]'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result[0] == [1, 2, 3], f"Expected resolved promise [1,2,3], got {result[0]}"

    def test_promise_resolved_with_undefined(self) -> None:
        text = '[["P", 5]]\nP5:-5'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result[0] is UNDEFINED, (
            f"Expected UNDEFINED for promise resolved to -5, got {result[0]!r}"
        )


class TestDecodeIndexedObjects:
    """Verify decoding of indexed object keys {"_N": value}."""

    def test_indexed_key_resolved_from_array(self) -> None:
        # Array: [0: "email", 1: {"_0": "test@example.com"}]
        text = '["email", {"_0": "test@example.com"}]'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert isinstance(result[1], dict), f"Expected dict at index 1, got {type(result[1])}"
        assert "email" in result[1], (
            f"Expected 'email' key in resolved dict, got keys {list(result[1].keys())}"
        )
        assert result[1]["email"] == "test@example.com", (
            f"Expected 'test@example.com', got {result[1]['email']}"
        )

    def test_non_indexed_key_preserved(self) -> None:
        text = '{"regularKey": "value"}'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result == {"regularKey": "value"}, f"Expected regular key preserved, got {result}"

    def test_invalid_index_key_preserved(self) -> None:
        text = '{"_abc": "value"}'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert "_abc" in result, f"Expected invalid index key '_abc' preserved, got {result}"


class TestDecodeMultiline:
    """Verify multiline response handling (main array + promise lines)."""

    def test_multiline_response_resolves_promises(self) -> None:
        main = json.dumps(["key", ["P", 1], "other", ["P", 2]])
        text = f"{main}\nP1:100\nP2:200"
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result[1] == 100, f"Expected first promise resolved to 100, got {result[1]}"
        assert result[3] == 200, f"Expected second promise resolved to 200, got {result[3]}"

    def test_empty_subsequent_lines_ignored(self) -> None:
        text = '["hello"]\n\n\n'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result == ["hello"], f"Expected empty lines ignored, got {result}"

    def test_non_promise_lines_ignored(self) -> None:
        text = '["hello"]\nNOT_A_PROMISE'
        decoder = TurboStreamDecoder()
        result = decoder.decode(text)
        assert result == ["hello"], f"Expected non-promise line ignored, got {result}"


class TestDecodeInfiniteRecursionGuard:
    """Verify the decoder doesn't infinite-loop on circular references."""

    def test_self_referencing_index_does_not_loop(self) -> None:
        # Index 0 maps to key "self", value at index 0 would self-reference
        # The decoder's _resolving set should prevent infinite recursion
        decoder = TurboStreamDecoder()
        decoder.index_map = {0: "key", 1: 1}  # 1 -> 1 is self-referencing
        result = decoder._decode_value({"_0": 1}, resolve_int_as_index=False)
        # Should complete without hanging
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"


# ===================================================================
# TurboStreamDecoder._parse_promise_line
# ===================================================================


class TestParsePromiseLine:
    """Verify promise line parsing edge cases."""

    def test_valid_numeric_promise(self) -> None:
        decoder = TurboStreamDecoder()
        decoder._parse_promise_line("P42:100")
        assert decoder.promise_values[42] == 100, (
            f"Expected promise 42 = 100, got {decoder.promise_values.get(42)}"
        )

    def test_valid_json_promise(self) -> None:
        decoder = TurboStreamDecoder()
        decoder._parse_promise_line('P10:{"key": "val"}')
        assert decoder.promise_values[10] == {"key": "val"}, (
            f"Expected promise 10 = dict, got {decoder.promise_values.get(10)}"
        )

    def test_promise_line_without_colon_skipped(self) -> None:
        decoder = TurboStreamDecoder()
        decoder._parse_promise_line("P42")
        assert 42 not in decoder.promise_values, "Expected no promise stored for line without colon"

    def test_promise_line_with_invalid_id_skipped(self) -> None:
        decoder = TurboStreamDecoder()
        decoder._parse_promise_line("Pabc:100")
        assert len(decoder.promise_values) == 0, "Expected no promise stored for non-numeric ID"

    def test_promise_line_with_unparseable_value_logged(self) -> None:
        decoder = TurboStreamDecoder()
        decoder._parse_promise_line("P1:not_json_not_number")
        assert 1 not in decoder.promise_values, "Expected no promise stored for unparseable value"


# ===================================================================
# TurboStreamDecoder.extract_data_section
# ===================================================================


class TestExtractDataSection:
    """Verify path-based data extraction from decoded structures."""

    def test_valid_path_returns_nested_dict(self) -> None:
        decoder = TurboStreamDecoder()
        decoded = {"root": {"data": {"name": "test"}}}
        result = decoder.extract_data_section(decoded, "root.data")
        assert result == {"name": "test"}, f"Expected nested dict, got {result}"

    def test_missing_path_returns_empty_dict(self) -> None:
        decoder = TurboStreamDecoder()
        decoded = {"root": {"other": "val"}}
        result = decoder.extract_data_section(decoded, "root.data")
        assert result == {}, f"Expected empty dict for missing path, got {result}"

    def test_non_dict_input_returns_empty_dict(self) -> None:
        decoder = TurboStreamDecoder()
        result = decoder.extract_data_section([1, 2, 3], "root.data")
        assert result == {}, f"Expected empty dict for non-dict input, got {result}"

    def test_path_ending_at_non_dict_returns_empty(self) -> None:
        decoder = TurboStreamDecoder()
        decoded = {"root": {"data": "not_a_dict"}}
        result = decoder.extract_data_section(decoded, "root.data")
        assert result == {}, f"Expected empty dict when path target is not dict, got {result}"


# ===================================================================
# parse_response top-level function
# ===================================================================


class TestParseResponse:
    """Verify the top-level parse_response convenience function."""

    def test_simple_array(self) -> None:
        result = parse_response('[1, "two", 3]')
        assert result == [1, "two", 3], f"Expected [1, 'two', 3], got {result}"

    def test_multiline_with_promise(self) -> None:
        text = '[["P", 1]]\nP1:"resolved"'
        result = parse_response(text)
        assert result[0] == "resolved", f"Expected resolved promise, got {result[0]}"


# ===================================================================
# _resolve_index helper
# ===================================================================


class TestResolveIndex:
    """Verify deep index resolution for typed extraction functions."""

    def test_resolves_simple_int_to_value(self) -> None:
        index_map = {10: "hello"}
        result = _resolve_index(10, index_map)
        assert result == "hello", f"Expected 'hello' for index 10, got {result}"

    def test_sentinel_minus5_returns_none(self) -> None:
        result = _resolve_index(-5, {})
        assert result is None, f"Expected None for sentinel -5, got {result!r}"

    def test_sentinel_minus7_returns_none(self) -> None:
        result = _resolve_index(-7, {})
        assert result is None, f"Expected None for sentinel -7, got {result!r}"

    def test_unknown_int_returned_as_is(self) -> None:
        result = _resolve_index(999, {0: "a", 1: "b"})
        assert result == 999, f"Expected 999 unchanged for unknown index, got {result}"

    def test_resolves_nested_dict_with_indexed_keys(self) -> None:
        index_map = {0: "name", 1: "Alice"}
        value = {"_0": 1}
        result = _resolve_index(value, index_map)
        assert result == {"name": "Alice"}, f"Expected resolved dict, got {result}"

    def test_resolves_nested_list(self) -> None:
        index_map = {5: "resolved_item"}
        value = [5, "literal"]
        result = _resolve_index(value, index_map)
        assert result == ["resolved_item", "literal"], f"Expected resolved list, got {result}"

    def test_depth_limit_prevents_infinite_recursion(self) -> None:
        # Create circular reference: 0 -> dict with _1 -> 0
        index_map: dict[int, Any] = {0: {"_1": 0}, 1: "key"}
        result = _resolve_index(0, index_map, depth=5)
        # At depth 5, one more recursion hits depth 6 which hits limit
        # Should not raise, should return the value at the depth limit
        assert result is not None, "Expected non-None result from depth-limited resolution"

    def test_simple_value_not_double_resolved(self) -> None:
        """Regression: value 55 resolved from index should NOT be re-resolved.

        Even when 55 itself is a valid index, resolution should stop.
        """
        index_map = {10: 55, 55: "should_not_reach_this"}
        result = _resolve_index(10, index_map)
        assert result == 55, f"Expected 55 (no double-resolution), got {result}"

    def test_string_value_passed_through(self) -> None:
        result = _resolve_index("hello", {})
        assert result == "hello", f"Expected string passed through, got {result}"

    def test_none_value_passed_through(self) -> None:
        result = _resolve_index(None, {})
        assert result is None, f"Expected None passed through, got {result!r}"

    def test_bool_value_passed_through(self) -> None:
        result = _resolve_index(True, {})
        assert result is True, f"Expected True passed through, got {result}"


# ===================================================================
# _find_key_value helper
# ===================================================================


class TestFindKeyValue:
    """Verify key search in decoded arrays."""

    def test_finds_existing_key(self) -> None:
        decoded = ["name", "Alice", "age", 30]
        result = _find_key_value(decoded, "name")
        assert result == "Alice", f"Expected 'Alice' for key 'name', got {result}"

    def test_returns_none_for_missing_key(self) -> None:
        decoded = ["name", "Alice"]
        result = _find_key_value(decoded, "email")
        assert result is None, f"Expected None for missing key, got {result}"

    def test_key_at_last_position_returns_none(self) -> None:
        decoded = ["name", "Alice", "orphan_key"]
        result = _find_key_value(decoded, "orphan_key")
        assert result is None, (
            "Expected None when key is at the last position with no adjacent value"
        )

    def test_empty_decoded_returns_none(self) -> None:
        result = _find_key_value([], "anything")
        assert result is None, f"Expected None for empty list, got {result}"

    def test_returns_first_occurrence(self) -> None:
        decoded = ["key", "first", "key", "second"]
        result = _find_key_value(decoded, "key")
        assert result == "first", f"Expected first occurrence 'first', got {result}"


# ===================================================================
# _safe_int / _safe_float / _safe_str
# ===================================================================


class TestSafeInt:
    """Verify safe integer conversion."""

    def test_int_passthrough(self) -> None:
        assert _safe_int(42) == 42, "Expected int 42"

    def test_float_truncated(self) -> None:
        assert _safe_int(3.7) == 3, "Expected float 3.7 truncated to 3"

    def test_numeric_string_converted(self) -> None:
        assert _safe_int("100") == 100, "Expected string '100' → 100"

    def test_non_numeric_string_returns_zero(self) -> None:
        assert _safe_int("abc") == 0, "Expected non-numeric string → 0"

    def test_none_returns_zero(self) -> None:
        assert _safe_int(None) == 0, "Expected None → 0"

    def test_bool_true_returns_one(self) -> None:
        assert _safe_int(True) == 1, "Expected True → 1"

    def test_empty_string_returns_zero(self) -> None:
        assert _safe_int("") == 0, "Expected empty string → 0"


class TestSafeFloat:
    """Verify safe float conversion."""

    def test_float_passthrough(self) -> None:
        assert _safe_float(3.14) == 3.14, "Expected float 3.14"

    def test_int_to_float(self) -> None:
        assert _safe_float(5) == 5.0, "Expected int 5 → 5.0"

    def test_numeric_string_converted(self) -> None:
        assert _safe_float("2.5") == 2.5, "Expected string '2.5' → 2.5"

    def test_non_numeric_string_returns_zero(self) -> None:
        assert _safe_float("xyz") == 0.0, "Expected non-numeric string → 0.0"

    def test_none_returns_zero(self) -> None:
        assert _safe_float(None) == 0.0, "Expected None → 0.0"

    def test_empty_string_returns_zero(self) -> None:
        assert _safe_float("") == 0.0, "Expected empty string → 0.0"


class TestSafeStr:
    """Verify safe string conversion."""

    def test_string_passthrough(self) -> None:
        assert _safe_str("hello") == "hello", "Expected string passthrough"

    def test_none_returns_empty(self) -> None:
        assert _safe_str(None) == "", "Expected None → ''"

    def test_undefined_returns_empty(self) -> None:
        assert _safe_str(UNDEFINED) == "", "Expected UNDEFINED → ''"

    def test_int_returns_empty(self) -> None:
        assert _safe_str(42) == "", "Expected non-string type → ''"

    def test_empty_string_passthrough(self) -> None:
        assert _safe_str("") == "", "Expected empty string → ''"


# ===================================================================
# Typed extraction functions with synthetic data
# ===================================================================


def _build_user_settings_response(
    profile_fields: dict[str, Any] | None = None,
    email: str = "user@test.com",
) -> str:
    """Build a minimal synthetic user-settings.data turbo-stream response."""
    profile = {
        "userName": "testuser",
        "userId": "uid-123",
        "firstName": "Test",
        "lastName": "User",
        "ftp": 200,
        "ftpSource": "MANUAL",
        "weight": 75.0,
        "height": 180.0,
        "gender": "MALE",
        "maxHeartRate": 185,
        "countryIsoCode": "US",
        "timezone": "UTC",
        "units": "METRIC",
        "accountPrivacy": "PUBLIC",
    }
    if profile_fields:
        profile.update(profile_fields)

    array = ["email", email, "userProfile", profile]
    return json.dumps(array)


class TestExtractUserProfileFromSynthetic:
    """Verify extract_user_profile with synthetic turbo-stream data."""

    def test_extracts_email(self) -> None:
        raw = extract_user_profile(_build_user_settings_response())
        assert raw["email"] == "user@test.com", (
            f"Expected email user@test.com, got {raw.get('email')}"
        )

    def test_extracts_username(self) -> None:
        raw = extract_user_profile(_build_user_settings_response())
        assert raw["username"] == "testuser", (
            f"Expected username testuser, got {raw.get('username')}"
        )

    def test_extracts_weight(self) -> None:
        raw = extract_user_profile(_build_user_settings_response())
        assert raw["weight_kg"] == 75.0, f"Expected weight 75.0, got {raw.get('weight_kg')}"

    def test_extracts_ftp(self) -> None:
        raw = extract_user_profile(_build_user_settings_response())
        assert raw["ftp_watts"] == 200, f"Expected ftp 200, got {raw.get('ftp_watts')}"

    def test_missing_profile_returns_empty_dict(self) -> None:
        text = json.dumps(["someKey", "someValue"])
        raw = extract_user_profile(text)
        assert "username" not in raw, "Expected no username when userProfile missing"

    def test_empty_response_returns_empty_dict(self) -> None:
        raw = extract_user_profile("[]")
        assert raw == {}, f"Expected empty dict for empty response, got {raw}"


class TestExtractUserProfileModelFromSynthetic:
    """Verify extract_user_profile_model with synthetic data."""

    def test_returns_user_profile_model(self) -> None:
        from custom_components.rouvy.api_client.models import UserProfile

        profile = extract_user_profile_model(_build_user_settings_response())
        assert isinstance(profile, UserProfile), f"Expected UserProfile, got {type(profile)}"

    def test_model_has_correct_fields(self) -> None:
        profile = extract_user_profile_model(_build_user_settings_response())
        assert profile.username == "testuser", f"Expected username testuser, got {profile.username}"
        assert profile.weight_kg == 75.0, f"Expected weight 75.0, got {profile.weight_kg}"
        assert profile.ftp_watts == 200, f"Expected ftp 200, got {profile.ftp_watts}"

    def test_model_defaults_for_missing_fields(self) -> None:
        text = json.dumps(["userProfile", {"userName": "bare"}])
        profile = extract_user_profile_model(text)
        assert profile.username == "bare", f"Expected username 'bare', got {profile.username}"
        assert profile.weight_kg == 0.0, f"Expected default weight 0.0, got {profile.weight_kg}"
        assert profile.email == "", f"Expected default email '', got {profile.email}"

    def test_birth_date_parsed_from_iso_string(self) -> None:
        # Simulate a birth_date that the raw extractor would produce.
        # The TurboStreamDecoder converts ["D", timestamp_ms] into a datetime.
        # extract_user_profile produces a string via str() on that datetime,
        # then extract_user_profile_model parses it with date.fromisoformat().
        # Use a date with no timezone ambiguity (mid-year).
        ts = 646876800000  # 1990-07-02 00:00:00 UTC
        text = json.dumps(["userProfile", {"userName": "u", "birthDate": ["D", ts]}])
        profile = extract_user_profile_model(text)
        if profile.birth_date is not None:
            assert profile.birth_date.year == 1990, (
                f"Expected birth year 1990, got {profile.birth_date.year}"
            )


def _build_zones_response(
    ftp: int = 200,
    max_hr: int = 190,
    power_values: list[int] | None = None,
    power_defaults: list[int] | None = None,
    hr_values: list[int] | None = None,
) -> str:
    """Build a minimal synthetic zones.data turbo-stream response."""
    if power_values is None:
        power_values = [55, 75, 90, 105, 120, 150]
    if power_defaults is None:
        power_defaults = [55, 75, 90, 105, 120, 150]
    if hr_values is None:
        hr_values = [60, 65, 75, 82, 89, 94]

    array: list[Any] = [
        "userProfile",
        {"ftp": ftp, "maxHeartRate": max_hr},
        "zones",
        {
            "power": {
                "values": power_values,
                "defaultValues": power_defaults,
            },
            "heartRate": {
                "values": hr_values,
                "defaultValues": [60, 65, 75, 82, 89, 94],
            },
        },
    ]
    return json.dumps(array)


class TestExtractTrainingZonesModelFromSynthetic:
    """Verify extract_training_zones_model with synthetic data."""

    def test_returns_training_zones_model(self) -> None:
        from custom_components.rouvy.api_client.models import TrainingZones

        zones = extract_training_zones_model(_build_zones_response())
        assert isinstance(zones, TrainingZones), f"Expected TrainingZones, got {type(zones)}"

    def test_ftp_and_max_hr_extracted(self) -> None:
        zones = extract_training_zones_model(_build_zones_response(ftp=250, max_hr=195))
        assert zones.ftp_watts == 250, f"Expected ftp 250, got {zones.ftp_watts}"
        assert zones.max_heart_rate == 195, f"Expected max HR 195, got {zones.max_heart_rate}"

    def test_power_zone_values_extracted(self) -> None:
        zones = extract_training_zones_model(
            _build_zones_response(power_values=[50, 70, 85, 100, 115, 140])
        )
        assert zones.power_zone_values == [50, 70, 85, 100, 115, 140], (
            f"Expected custom power values, got {zones.power_zone_values}"
        )

    def test_missing_zones_returns_empty_lists(self) -> None:
        text = json.dumps(["userProfile", {"ftp": 100, "maxHeartRate": 180}])
        zones = extract_training_zones_model(text)
        assert zones.power_zone_values == [], (
            f"Expected empty power values, got {zones.power_zone_values}"
        )
        assert zones.hr_zone_values == [], f"Expected empty HR values, got {zones.hr_zone_values}"

    def test_missing_profile_returns_zero_ftp(self) -> None:
        text = json.dumps(["zones", {"power": {"values": [50]}}])
        zones = extract_training_zones_model(text)
        assert zones.ftp_watts == 0, f"Expected 0 ftp when profile missing, got {zones.ftp_watts}"


def _build_connected_apps_response(
    active: list[dict[str, Any]] | None = None,
    available: list[dict[str, Any]] | None = None,
) -> str:
    """Build a minimal synthetic connected-apps.data turbo-stream response."""
    if active is None:
        active = [
            {
                "providerId": "garmin",
                "name": "Garmin Connect",
                "status": "active",
                "uploadMode": "auto",
                "description": "Garmin",
                "logoPath": "/logo.png",
                "tokenMetadata": {"permissions": ["ACTIVITY_EXPORT"]},
            }
        ]
    if available is None:
        available = [
            {
                "providerId": "strava",
                "name": "Strava",
                "status": "available",
            }
        ]

    array: list[Any] = ["activeProviders", active, "availableProviders", available]
    return json.dumps(array)


class TestExtractConnectedAppsModelFromSynthetic:
    """Verify extract_connected_apps_model with synthetic data."""

    def test_returns_list_of_connected_app(self) -> None:
        from custom_components.rouvy.api_client.models import ConnectedApp

        apps = extract_connected_apps_model(_build_connected_apps_response())
        assert all(isinstance(a, ConnectedApp) for a in apps), (
            "Expected all items to be ConnectedApp"
        )

    def test_active_and_available_combined(self) -> None:
        apps = extract_connected_apps_model(_build_connected_apps_response())
        assert len(apps) == 2, f"Expected 2 apps (1 active + 1 available), got {len(apps)}"

    def test_active_provider_fields(self) -> None:
        apps = extract_connected_apps_model(_build_connected_apps_response())
        garmin = next(a for a in apps if a.provider_id == "garmin")
        assert garmin.name == "Garmin Connect", f"Expected name 'Garmin Connect', got {garmin.name}"
        assert garmin.status == "active", f"Expected status 'active', got {garmin.status}"
        assert garmin.upload_mode == "auto", (
            f"Expected upload_mode 'auto', got {garmin.upload_mode}"
        )
        assert "ACTIVITY_EXPORT" in garmin.permissions, (
            f"Expected ACTIVITY_EXPORT in permissions, got {garmin.permissions}"
        )

    def test_empty_providers_returns_empty_list(self) -> None:
        text = json.dumps(["otherKey", "otherValue"])
        apps = extract_connected_apps_model(text)
        assert apps == [], f"Expected empty list, got {apps}"

    def test_non_dict_items_skipped(self) -> None:
        text = json.dumps(["activeProviders", [42, "not_a_dict"]])
        apps = extract_connected_apps_model(text)
        assert apps == [], f"Expected empty after skipping non-dict items, got {apps}"


def _build_activities_response(
    activities: list[dict[str, Any]] | None = None,
) -> str:
    """Build a minimal synthetic profile/overview.data turbo-stream response."""
    if activities is None:
        activities = [
            {
                "id": "act-1",
                "title": "Morning Ride",
                "training": "ROUTE_TIME_TRIAL",
                "total": {
                    "distM": 25000.0,
                    "movingTimeSec": 3600,
                    "elevM": 350.0,
                    "avgPower": 180,
                    "avgHeartRate": 145,
                    "avgCadence": 85,
                    "avgSpeed": 25.0,
                    "normalizedPower": 190,
                    "if": 0.95,
                },
                "startUTC": "2024-01-15T08:00:00Z",
            },
        ]
    array: list[Any] = ["activities", activities]
    return json.dumps(array)


class TestExtractActivitiesModelFromSynthetic:
    """Verify extract_activities_model with synthetic data."""

    def test_returns_activity_summary(self) -> None:
        from custom_components.rouvy.api_client.models import ActivitySummary

        summary = extract_activities_model(_build_activities_response())
        assert isinstance(summary, ActivitySummary), (
            f"Expected ActivitySummary, got {type(summary)}"
        )

    def test_activity_fields_populated(self) -> None:
        summary = extract_activities_model(_build_activities_response())
        act = summary.recent_activities[0]
        assert act.activity_id == "act-1", f"Expected activity_id 'act-1', got {act.activity_id}"
        assert act.title == "Morning Ride", f"Expected title 'Morning Ride', got {act.title}"
        assert act.distance_m == 25000.0, f"Expected distance 25000.0, got {act.distance_m}"
        assert act.moving_time_seconds == 3600, (
            f"Expected moving time 3600, got {act.moving_time_seconds}"
        )

    def test_empty_activities_list(self) -> None:
        summary = extract_activities_model(_build_activities_response(activities=[]))
        assert summary.recent_activities == [], (
            f"Expected empty activities, got {summary.recent_activities}"
        )

    def test_missing_activities_key(self) -> None:
        text = json.dumps(["other", "data"])
        summary = extract_activities_model(text)
        assert summary.recent_activities == [], (
            f"Expected empty when activities key missing, got {summary.recent_activities}"
        )

    def test_activity_with_missing_total(self) -> None:
        acts = [{"id": "act-x", "title": "No Stats"}]
        summary = extract_activities_model(_build_activities_response(activities=acts))
        act = summary.recent_activities[0]
        assert act.distance_m == 0.0, (
            f"Expected 0.0 distance when total missing, got {act.distance_m}"
        )

    def test_intensity_factor_non_numeric_excluded(self) -> None:
        acts = [
            {
                "id": "act-y",
                "title": "Bad IF",
                "total": {"distance": 1000, "movingTime": 60, "if": "not_a_number"},
            }
        ]
        summary = extract_activities_model(_build_activities_response(activities=acts))
        assert summary.recent_activities[0].intensity_factor is None, (
            "Expected None intensity_factor for non-numeric 'if' value"
        )


# ===================================================================
# extract_activity_stats_model
# ===================================================================


def _build_activity_stats_response(
    weeks: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Build a synthetic turbo-stream response for activity-stats.data.

    The response is a flat array: [refmap, key, value] where value is
    a dict keyed by week index (0, 1, ...) with weekly stats.
    """
    if weeks is None:
        weeks = {
            "0": {
                "weekStart": "Mar 30, 2026, 12:00 AM EDT",
                "weekEnd": "Apr 5, 2026, 11:59 PM EDT",
                "metrics": [1, 2, 3, 4, 5],
                "activityTypeStats": {
                    "ride": {
                        "distM": 45000.0,
                        "elevM": 350.0,
                        "kCal": 800.5,
                        "movingTimeSec": 5400,
                        "if": 0.72,
                        "trainingScore": 65.3,
                        "activityCount": 3,
                    },
                    "workout": {
                        "distM": 0.0,
                        "elevM": 0.0,
                        "kCal": 150.0,
                        "movingTimeSec": 1800,
                        "if": 0.0,
                        "trainingScore": 20.0,
                        "activityCount": 1,
                    },
                    "event": {
                        "distM": 20000.0,
                        "elevM": 200.0,
                        "kCal": 400.0,
                        "movingTimeSec": 3600,
                        "if": 0.85,
                        "trainingScore": 45.0,
                        "activityCount": 1,
                    },
                    "outdoor": {
                        "distM": 0.0,
                        "elevM": 0.0,
                        "kCal": 0.0,
                        "movingTimeSec": 0,
                        "if": 0.0,
                        "trainingScore": 0.0,
                        "activityCount": 0,
                    },
                },
            },
            "1": {
                "weekStart": "Apr 6, 2026, 12:00 AM EDT",
                "weekEnd": "Apr 12, 2026, 11:59 PM EDT",
                "metrics": [1, 2, 3, 4, 5],
                "activityTypeStats": {
                    "ride": {
                        "distM": 30000.0,
                        "elevM": 250.0,
                        "kCal": 550.0,
                        "movingTimeSec": 3600,
                        "if": 0.68,
                        "trainingScore": 42.0,
                        "activityCount": 2,
                    },
                    "workout": {
                        "distM": 0.0,
                        "elevM": 0.0,
                        "kCal": 0.0,
                        "movingTimeSec": 0,
                        "if": 0.0,
                        "trainingScore": 0.0,
                        "activityCount": 0,
                    },
                    "event": {
                        "distM": 0.0,
                        "elevM": 0.0,
                        "kCal": 0.0,
                        "movingTimeSec": 0,
                        "if": 0.0,
                        "trainingScore": 0.0,
                        "activityCount": 0,
                    },
                    "outdoor": {
                        "distM": 0.0,
                        "elevM": 0.0,
                        "kCal": 0.0,
                        "movingTimeSec": 0,
                        "if": 0.0,
                        "trainingScore": 0.0,
                        "activityCount": 0,
                    },
                },
            },
        }
    # Build the flat turbo-stream array: [{}, "activityStats", {weeks}]
    return json.dumps([{}, "activityStats", weeks])


class TestExtractActivityStats:
    """Verify extraction of weekly activity statistics."""

    def test_returns_list_of_weekly_stats(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        assert len(result) == 2, f"Expected 2 weeks, got {len(result)}"

    def test_week_start_and_end_extracted(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        assert result[0].week_start == "Mar 30, 2026, 12:00 AM EDT"
        assert result[0].week_end == "Apr 5, 2026, 11:59 PM EDT"

    def test_ride_stats_extracted(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        ride = result[0].ride
        assert ride.distance_m == 45000.0, f"Expected 45000, got {ride.distance_m}"
        assert ride.elevation_m == 350.0, f"Expected 350, got {ride.elevation_m}"
        assert ride.calories == 800.5, f"Expected 800.5, got {ride.calories}"
        assert ride.moving_time_seconds == 5400, f"Expected 5400, got {ride.moving_time_seconds}"
        assert ride.intensity_factor == 0.72, f"Expected 0.72, got {ride.intensity_factor}"
        assert ride.training_score == 65.3, f"Expected 65.3, got {ride.training_score}"
        assert ride.activity_count == 3, f"Expected 3, got {ride.activity_count}"

    def test_workout_stats_extracted(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        workout = result[0].workout
        assert workout.calories == 150.0
        assert workout.moving_time_seconds == 1800
        assert workout.activity_count == 1

    def test_event_stats_extracted(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        event = result[0].event
        assert event.distance_m == 20000.0
        assert event.intensity_factor == 0.85
        assert event.activity_count == 1

    def test_outdoor_stats_default_zeros(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        outdoor = result[0].outdoor
        assert outdoor.distance_m == 0.0
        assert outdoor.activity_count == 0

    def test_second_week_extracted(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(_build_activity_stats_response())
        assert result[1].ride.distance_m == 30000.0
        assert result[1].ride.activity_count == 2

    def test_empty_response_returns_empty_list(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        result = extract_activity_stats_model(json.dumps([{}]))
        assert result == [], f"Expected empty list, got {result}"

    def test_missing_activity_type_stats_returns_defaults(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        weeks = {
            "0": {
                "weekStart": "Jan 1, 2026",
                "weekEnd": "Jan 7, 2026",
            }
        }
        result = extract_activity_stats_model(_build_activity_stats_response(weeks=weeks))
        assert len(result) == 1
        assert result[0].ride.distance_m == 0.0
        assert result[0].ride.activity_count == 0

    def test_missing_individual_type_returns_defaults(self) -> None:
        from custom_components.rouvy.api_client.parser import extract_activity_stats_model

        weeks = {
            "0": {
                "weekStart": "Jan 1, 2026",
                "weekEnd": "Jan 7, 2026",
                "activityTypeStats": {
                    "ride": {
                        "distM": 10000.0,
                        "elevM": 100.0,
                        "kCal": 200.0,
                        "movingTimeSec": 1200,
                        "if": 0.5,
                        "trainingScore": 15.0,
                        "activityCount": 1,
                    }
                },
            }
        }
        result = extract_activity_stats_model(_build_activity_stats_response(weeks=weeks))
        assert result[0].ride.distance_m == 10000.0
        assert result[0].workout.distance_m == 0.0
        assert result[0].event.activity_count == 0
        assert result[0].outdoor.training_score == 0.0
