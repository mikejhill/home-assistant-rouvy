"""Decoder for the turbo-stream wire format used by Remix single-fetch responses.

Reference: https://github.com/jacob-ebey/turbo-stream (v2 flat encoding).
The first line is a JSON array holding every value of the graph; containers refer to
other values by index. Later lines (``P<id>:<json>``) resolve deferred promises and
append more values to the same index space.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

from custom_components.rouvy.rouvy_api.exceptions import RouvyResponseError

type TurboValue = (
    bool
    | int
    | float
    | str
    | datetime
    | TaggedValue
    | list[TurboValue]
    | dict[str, TurboValue]
    | None
)
type RawValue = bool | int | float | str | list[RawValue] | dict[str, RawValue] | None

HOLE: Final = -1
NAN: Final = -2
NEGATIVE_INFINITY: Final = -3
NEGATIVE_ZERO: Final = -4
NULL: Final = -5
POSITIVE_INFINITY: Final = -6
UNDEFINED: Final = -7

_CONSTANTS: Final[dict[int, float | None]] = {
    HOLE: None,
    NAN: math.nan,
    NEGATIVE_INFINITY: -math.inf,
    NEGATIVE_ZERO: -0.0,
    NULL: None,
    POSITIVE_INFINITY: math.inf,
    UNDEFINED: None,
}
_LITERAL_TAGS: Final = frozenset({"U", "B", "Y", "R"})


@dataclass(frozen=True, slots=True)
class TaggedValue:
    """A typed turbo-stream value without a native Python equivalent (e.g. a redirect)."""

    tag: str
    args: tuple[TurboValue, ...]


class TurboStreamDecoder:
    """Decode one complete turbo-stream response body into Python values."""

    def __init__(self) -> None:
        self._values: list[RawValue] = []
        self._hydrated: dict[int, TurboValue] = {}
        self._promises: dict[int, int] = {}
        self._rejected: set[int] = set()

    def decode(self, text: str) -> TurboValue:
        """Return the root value of a turbo-stream body.

        Raises:
            RouvyResponseError: If the body is not valid turbo-stream.
        """
        lines = [line for line in text.strip().splitlines() if line.strip()]
        if not lines:
            msg = "Empty turbo-stream response"
            raise RouvyResponseError(msg)

        # Index the main payload and every promise resolution before hydrating
        root_index = self._append(self._parse_json(lines[0]))
        for line in lines[1:]:
            self._register_promise(line)

        try:
            return self._hydrate(root_index)
        except RecursionError as err:
            msg = "turbo-stream payload is nested too deeply"
            raise RouvyResponseError(msg) from err

    # Internals

    @staticmethod
    def _parse_json(text: str) -> RawValue:
        """Parse one JSON line."""
        try:
            # json.loads only ever produces JSON values, which RawValue models exactly
            parsed = cast("RawValue", json.loads(text))
        except json.JSONDecodeError as err:
            msg = f"Invalid JSON in turbo-stream line: {err.msg} at column {err.colno}"
            raise RouvyResponseError(msg) from err
        return parsed

    def _append(self, chunk: RawValue) -> int:
        """Add a parsed chunk to the value table and return the index of its root."""
        if isinstance(chunk, int) and not isinstance(chunk, bool):
            return chunk
        if not isinstance(chunk, list) or not chunk:
            msg = "turbo-stream chunk must be a non-empty array or an index"
            raise RouvyResponseError(msg)
        start = len(self._values)
        self._values.extend(chunk)
        return start

    def _register_promise(self, line: str) -> None:
        """Record the value index for a ``P<id>:`` or ``E<id>:`` line."""
        kind, separator, rest = line.partition(":")
        if not separator or kind[:1] not in {"P", "E"} or not kind[1:].isdigit():
            msg = f"Unrecognised turbo-stream line prefix: {kind[:20]!r}"
            raise RouvyResponseError(msg)
        promise_id = int(kind[1:])
        index = self._append(self._parse_json(rest))
        self._promises[promise_id] = index
        if kind[0] == "E":
            self._rejected.add(promise_id)

    def _hydrate(self, index: int) -> TurboValue:
        """Return the Python value stored at an index."""
        if index < 0:
            return self._constant(index)
        if index in self._hydrated:
            return self._hydrated[index]
        if index >= len(self._values):
            msg = f"turbo-stream reference {index} is out of range"
            raise RouvyResponseError(msg)

        raw = self._values[index]
        if isinstance(raw, dict):
            return self._hydrate_object(index, raw)
        if isinstance(raw, list):
            if raw and isinstance(raw[0], str):
                return self._hydrate_tagged(index, raw[0], raw[1:])
            return self._hydrate_array(index, raw)
        self._hydrated[index] = raw
        return raw

    @staticmethod
    def _constant(index: int) -> TurboValue:
        """Return the value of a negative sentinel index."""
        if index not in _CONSTANTS:
            msg = f"Unknown turbo-stream constant {index}"
            raise RouvyResponseError(msg)
        return _CONSTANTS[index]

    def _hydrate_object(self, index: int, raw: dict[str, RawValue]) -> TurboValue:
        """Hydrate a ``{"_<keyIndex>": valueIndex}`` object."""
        result: dict[str, TurboValue] = {}
        self._hydrated[index] = result
        for encoded_key, value_index in raw.items():
            key = self._hydrate(self._reference(encoded_key.removeprefix("_")))
            result[key if isinstance(key, str) else str(key)] = self._hydrate(
                self._reference(value_index)
            )
        return result

    def _hydrate_array(self, index: int, raw: list[RawValue]) -> TurboValue:
        """Hydrate a plain array of value indices."""
        result: list[TurboValue] = []
        self._hydrated[index] = result
        result.extend(self._hydrate(self._reference(item)) for item in raw)
        return result

    def _hydrate_tagged(self, index: int, tag: str, args: list[RawValue]) -> TurboValue:
        """Hydrate a typed array such as a date, promise, set, map, or plugin value."""
        match tag:
            case "D":
                value: TurboValue = self._date(args)
            case "P":
                value = self._promise(self._reference(args[0]) if args else -1)
            case "Z":
                value = self._hydrate(self._reference(args[0]) if args else NULL)
            case "S":
                value = [self._hydrate(self._reference(item)) for item in args]
            case "M" | "N":
                value = self._pairs(args)
            case _ if tag in _LITERAL_TAGS:
                value = TaggedValue(tag, tuple(a for a in args if isinstance(a, str | int | float)))
            case _:
                value = TaggedValue(tag, tuple(self._hydrate(self._reference(a)) for a in args))
        self._hydrated[index] = value
        return value

    def _promise(self, promise_id: int) -> TurboValue:
        """Return the resolved value of a deferred promise, or None when unresolved."""
        if promise_id not in self._promises or promise_id in self._rejected:
            return None
        return self._hydrate(self._promises[promise_id])

    def _pairs(self, args: list[RawValue]) -> dict[str, TurboValue]:
        """Hydrate alternating key/value indices into a dict."""
        result: dict[str, TurboValue] = {}
        for key_index, value_index in zip(args[::2], args[1::2], strict=False):
            key = self._hydrate(self._reference(key_index))
            result[key if isinstance(key, str) else str(key)] = self._hydrate(
                self._reference(value_index)
            )
        return result

    @staticmethod
    def _date(args: list[RawValue]) -> datetime | None:
        """Convert a millisecond epoch timestamp into an aware datetime."""
        stamp = args[0] if args else None
        if (
            not isinstance(stamp, int | float)
            or isinstance(stamp, bool)
            or not math.isfinite(stamp)
        ):
            return None
        try:
            return datetime.fromtimestamp(stamp / 1000, tz=UTC)
        except OverflowError, OSError, ValueError:
            return None

    @staticmethod
    def _reference(raw: RawValue | str) -> int:
        """Convert an encoded reference into an integer index."""
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.lstrip("-").isdigit():
            return int(raw)
        msg = f"Invalid turbo-stream reference {raw!r}"
        raise RouvyResponseError(msg)
