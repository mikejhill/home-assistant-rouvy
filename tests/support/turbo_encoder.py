"""Turbo-stream encoder used to build realistic Rouvy responses in tests."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from rouvy_api.turbo_stream import (
    NAN,
    NEGATIVE_INFINITY,
    NEGATIVE_ZERO,
    NULL,
    POSITIVE_INFINITY,
    UNDEFINED,
)

type EncodedValue = (
    bool
    | int
    | float
    | str
    | datetime
    | Tagged
    | Deferred
    | Undefined
    | list[EncodedValue]
    | dict[str, EncodedValue]
    | None
)
type FlatValue = bool | int | float | str | list[FlatValue] | dict[str, FlatValue] | None


@dataclass(frozen=True, slots=True)
class Deferred:
    """A value sent later on its own ``P<id>:`` line, like a Remix deferred promise."""

    value: EncodedValue


@dataclass(frozen=True, slots=True)
class Tagged:
    """A typed turbo-stream value such as ``["SingleFetchRedirect", ...]``."""

    tag: str
    args: tuple[EncodedValue, ...]


@dataclass(frozen=True, slots=True)
class Undefined:
    """JavaScript ``undefined``."""


UNDEFINED_VALUE: Final = Undefined()


class TurboStreamEncoder:
    """Flatten Python values into turbo-stream text (the inverse of TurboStreamDecoder)."""

    def __init__(self) -> None:
        self._values: list[FlatValue] = []
        self._primitive_index: dict[tuple[str, FlatValue], int] = {}
        self._object_index: dict[int, int] = {}
        self._pending: list[tuple[int, EncodedValue]] = []
        self._next_promise = 1

    def encode(self, value: EncodedValue) -> str:
        """Return the turbo-stream body for a value graph."""
        root = self._flatten(value)
        first = json.dumps(self._values, separators=(",", ":")) if root >= 0 else str(root)
        lines = [first]
        while self._pending:
            promise_id, deferred = self._pending.pop(0)
            start = len(self._values)
            index = self._flatten(deferred)
            if index < start:
                lines.append(f"P{promise_id}:{index}")
            else:
                chunk = self._values[start:]
                lines.append(f"P{promise_id}:{json.dumps(chunk, separators=(',', ':'))}")
        return "\n".join(lines) + "\n"

    # Internals

    def _flatten(self, value: EncodedValue) -> int:
        """Return the index of a value, appending it when first seen."""
        constant = self._constant(value)
        if constant is not None:
            return constant
        if isinstance(value, bool | int | float | str):
            return self._primitive(value)
        if id(value) in self._object_index:
            return self._object_index[id(value)]
        index = self._reserve(value)
        self._values[index] = self._container(value)
        return index

    @staticmethod
    def _constant(value: EncodedValue) -> int | None:
        """Return the sentinel index for null, undefined, and special floats."""
        if value is None:
            return NULL
        if isinstance(value, Undefined):
            return UNDEFINED
        if isinstance(value, float) and not math.isfinite(value):
            if math.isnan(value):
                return NAN
            return POSITIVE_INFINITY if value > 0 else NEGATIVE_INFINITY
        if isinstance(value, float) and value == 0 and math.copysign(1, value) < 0:
            return NEGATIVE_ZERO
        return None

    def _primitive(self, value: bool | float | str) -> int:
        """Append a primitive once and reuse its index."""
        key = (type(value).__name__, value)
        if key not in self._primitive_index:
            self._primitive_index[key] = len(self._values)
            self._values.append(value)
        return self._primitive_index[key]

    def _reserve(self, value: EncodedValue) -> int:
        """Reserve a slot for a container so cycles resolve to it."""
        index = len(self._values)
        self._values.append(None)
        self._object_index[id(value)] = index
        return index

    def _container(self, value: EncodedValue) -> FlatValue:
        """Encode a container or typed value whose slot is already reserved."""
        if isinstance(value, datetime):
            return ["D", value.timestamp() * 1000]
        if isinstance(value, Deferred):
            promise_id = self._next_promise
            self._next_promise += 1
            self._pending.append((promise_id, value.value))
            return ["P", promise_id]
        if isinstance(value, Tagged):
            return [value.tag, *(self._flatten(arg) for arg in value.args)]
        if isinstance(value, list):
            return [self._flatten(item) for item in value]
        if isinstance(value, dict):
            return {f"_{self._flatten(key)}": self._flatten(item) for key, item in value.items()}
        msg = f"Cannot encode {type(value).__name__}"
        raise TypeError(msg)
