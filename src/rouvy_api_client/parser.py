"""
Parser for Rouvy API responses using turbo-stream format.

Rouvy uses the turbo-stream format from Remix (https://github.com/jacob-ebey/turbo-stream),
which is a streaming data format that supports more types than JSON and uses indexed
references to deduplicate repeated values.

Format characteristics:
- Main array with alternating keys and values
- Indexed references: {"_N": value} where N points to the key at index N in the array
- Special types:
  - Dates: ["D", timestamp_ms]
  - Promises: ["P", reference_id]
  - Negative indices: -5 represents undefined, -7 represents null
- Multi-line responses: First line is main data, subsequent lines resolve promises
"""

import json
import logging
from datetime import datetime
from typing import Any

LOGGER = logging.getLogger(__name__)

# Special sentinel values
UNDEFINED = object()  # Represents JavaScript undefined
NULL = None  # Represents JavaScript null


class TurboStreamDecoder:
    """Decoder for turbo-stream formatted responses."""

    def __init__(self):
        self.index_map: dict[int, Any] = {}
        self.promise_values: dict[int, Any] = {}

    def decode(self, response_text: str) -> dict[str, Any]:
        """
        Decode a turbo-stream formatted response.

        Args:
            response_text: Raw response text (may be multi-line)

        Returns:
            Decoded data structure
        """
        lines = response_text.strip().split("\n")
        main_data = json.loads(lines[0])

        # Parse promise resolutions from subsequent lines
        for line in lines[1:]:
            line = line.strip()
            if line and line.startswith("P"):
                self._parse_promise_line(line)

        # Build index map from the main array
        if isinstance(main_data, list):
            for i, item in enumerate(main_data):
                self.index_map[i] = item

        # Decode the main structure
        return self._decode_value(main_data)

    def _parse_promise_line(self, line: str) -> None:
        """Parse promise resolution lines like 'P132:-5' or 'P134:[...]'."""
        try:
            # Format: P<id>:<value>
            if ":" in line:
                parts = line.split(":", 1)
                promise_id = int(parts[0][1:])  # Remove 'P' prefix
                value_str = parts[1]

                # Try to parse as JSON
                try:
                    value = json.loads(value_str)
                    self.promise_values[promise_id] = value
                except json.JSONDecodeError:
                    # Might be a simple value like -5
                    if value_str.lstrip("-").isdigit():
                        self.promise_values[promise_id] = int(value_str)
                    else:
                        LOGGER.warning(f"Could not parse promise value: {value_str}")
        except Exception as e:
            LOGGER.warning(f"Error parsing promise line '{line}': {e}")

    def _decode_value(self, value: Any, resolve_int_as_index: bool = False) -> Any:
        """
        Recursively decode a value, resolving references and special types.

        Args:
            value: The value to decode
            resolve_int_as_index: If True, treat integers as index references to resolve
        """
        # Handle special numeric sentinels
        if isinstance(value, int):
            if value == -5:
                return UNDEFINED
            elif value == -7:
                return NULL
            # Only resolve as index if explicitly requested (for indexed object values)
            elif resolve_int_as_index and value in self.index_map:
                # Avoid infinite recursion
                if value not in getattr(self, "_resolving", set()):
                    if not hasattr(self, "_resolving"):
                        self._resolving = set()
                    self._resolving.add(value)
                    result = self._decode_value(
                        self.index_map[value], resolve_int_as_index=False
                    )
                    self._resolving.discard(value)
                    return result
            return value

        # Handle arrays
        if isinstance(value, list):
            # Check for special array formats
            if len(value) == 2:
                # Date format: ["D", timestamp_ms]
                if value[0] == "D" and isinstance(value[1], (int, float)):
                    try:
                        return datetime.fromtimestamp(value[1] / 1000)
                    except (ValueError, OSError):
                        LOGGER.warning(f"Invalid timestamp: {value[1]}")
                        return value

                # Promise reference: ["P", id]
                if value[0] == "P" and isinstance(value[1], int):
                    promise_id = value[1]
                    if promise_id in self.promise_values:
                        return self._decode_value(
                            self.promise_values[promise_id], resolve_int_as_index=False
                        )
                    else:
                        # Promise not yet resolved
                        return f"<Promise:{promise_id}>"

            # Regular array - decode each element (don't resolve ints as indices)
            return [
                self._decode_value(item, resolve_int_as_index=False) for item in value
            ]

        # Handle objects with indexed references
        if isinstance(value, dict):
            result = {}
            for key, val in value.items():
                if key.startswith("_"):
                    # This is an indexed reference for the KEY
                    try:
                        index = int(key[1:])
                        # Look up the actual key name
                        if index in self.index_map:
                            actual_key = self.index_map[index]
                            if isinstance(actual_key, str):
                                # VALUE of indexed keys should be resolved as index references
                                decoded_val = self._decode_value(
                                    val, resolve_int_as_index=True
                                )
                                result[actual_key] = decoded_val
                            else:
                                # Key itself needs decoding
                                decoded_key = self._decode_value(
                                    actual_key, resolve_int_as_index=False
                                )
                                if isinstance(decoded_key, str):
                                    decoded_val = self._decode_value(
                                        val, resolve_int_as_index=True
                                    )
                                    result[decoded_key] = decoded_val
                                else:
                                    result[key] = self._decode_value(
                                        val, resolve_int_as_index=False
                                    )
                        else:
                            result[key] = self._decode_value(
                                val, resolve_int_as_index=False
                            )
                    except ValueError:
                        result[key] = self._decode_value(
                            val, resolve_int_as_index=False
                        )
                else:
                    # Regular key - value is literal
                    result[key] = self._decode_value(val, resolve_int_as_index=False)
            return result

        # Return other types as-is
        return value

    def extract_data_section(
        self, decoded: Any, path: str = "root.data"
    ) -> dict[str, Any]:
        """
        Extract a specific data section from the decoded structure.

        Args:
            decoded: Decoded turbo-stream data
            path: Dot-separated path to the data section (default: "root.data")

        Returns:
            Extracted data section or empty dict if not found
        """
        if not isinstance(decoded, dict):
            return {}

        parts = path.split(".")
        current = decoded

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                LOGGER.debug(f"Path '{path}' not found in decoded data")
                return {}

        return current if isinstance(current, dict) else {}


def parse_response(response_text: str) -> dict[str, Any]:
    """
    Parse a Rouvy API response in turbo-stream format.

    Args:
        response_text: Raw response text

    Returns:
        Decoded data structure
    """
    decoder = TurboStreamDecoder()
    return decoder.decode(response_text)


def extract_user_profile(response_text: str) -> dict[str, Any]:
    """
    Extract user profile fields from user-settings response.

    Args:
        response_text: Raw user-settings.data response

    Returns:
        Dict with user profile fields
    """
    decoder = TurboStreamDecoder()
    decoded = decoder.decode(response_text)

    # Find the userProfile object in the decoded array
    user_data = {}
    array_data = decoded if isinstance(decoded, list) else []

    # First pass: find top-level email
    for i in range(len(array_data)):
        if array_data[i] == "email" and i + 1 < len(array_data):
            next_val = array_data[i + 1]
            if isinstance(next_val, str) and "@" in next_val:
                user_data["email"] = next_val
            break

    # Second pass: find userProfile object
    for i in range(len(array_data)):
        if array_data[i] == "userProfile" and i + 1 < len(array_data):
            profile_obj = array_data[i + 1]
            if isinstance(profile_obj, dict):
                # Extract fields from userProfile object
                if "userName" in profile_obj:
                    user_data["username"] = profile_obj["userName"]
                if "userId" in profile_obj:
                    user_data["user_id"] = profile_obj["userId"]
                if (
                    "firstName" in profile_obj
                    and profile_obj["firstName"] is not UNDEFINED
                ):
                    user_data["first_name"] = profile_obj["firstName"]
                if (
                    "lastName" in profile_obj
                    and profile_obj["lastName"] is not UNDEFINED
                ):
                    user_data["last_name"] = profile_obj["lastName"]
                if "ftp" in profile_obj:
                    user_data["ftp_watts"] = profile_obj["ftp"]
                if "weight" in profile_obj:
                    user_data["weight_kg"] = profile_obj["weight"]
                if "height" in profile_obj:
                    user_data["height_cm"] = profile_obj["height"]
                if "gender" in profile_obj:
                    user_data["gender"] = profile_obj["gender"]
                if "maxHeartRate" in profile_obj:
                    user_data["max_heart_rate"] = profile_obj["maxHeartRate"]
                if "countryIsoCode" in profile_obj:
                    user_data["country"] = profile_obj["countryIsoCode"]
                if "timezone" in profile_obj:
                    user_data["timezone"] = profile_obj["timezone"]
                if "units" in profile_obj:
                    user_data["units"] = profile_obj["units"]
                if "birthDate" in profile_obj:
                    birth_date = profile_obj["birthDate"]
                    if isinstance(birth_date, datetime):
                        user_data["birth_date"] = birth_date.date().isoformat()
            break

    return user_data
