"""Navigation helpers over decoded Remix single-fetch payloads."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from typing import Final

from rouvy_api.turbo_stream import TaggedValue, TurboStreamDecoder, TurboValue

_REDIRECT_TAG: Final = "SingleFetchRedirect"
_DISPLAY_FORMAT: Final = "%b %d, %Y, %I:%M %p UTC"


class Fields:
    """Typed, forgiving accessors over one decoded JSON object."""

    def __init__(self, data: Mapping[str, TurboValue]) -> None:
        self._data = data

    @classmethod
    def wrap(cls, value: TurboValue) -> Fields | None:
        """Return Fields for a dict value, otherwise None."""
        return cls(value) if isinstance(value, dict) else None

    @property
    def raw(self) -> Mapping[str, TurboValue]:
        """Return the underlying mapping."""
        return self._data

    def has(self, key: str) -> bool:
        """Return True when the key exists with a non-null value."""
        return self._data.get(key) is not None

    def text(self, key: str) -> str | None:
        """Return a non-empty string value."""
        value = self._data.get(key)
        return value if isinstance(value, str) and value else None

    def integer(self, key: str) -> int | None:
        """Return an integer value, accepting integral floats and numeric strings."""
        number = self.number(key)
        return round(number) if number is not None else None

    def number(self, key: str) -> float | None:
        """Return a finite numeric value as float."""
        value = self._data.get(key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value) if math.isfinite(value) else None
        if isinstance(value, str):
            try:
                parsed = float(value)
            except ValueError:
                return None
            return parsed if math.isfinite(parsed) else None
        return None

    def flag(self, key: str) -> bool:
        """Return a boolean value, treating anything but True as False."""
        return self._data.get(key) is True

    def mapping(self, key: str) -> Fields | None:
        """Return a nested object."""
        return Fields.wrap(self._data.get(key))

    def records(self, key: str) -> list[Fields]:
        """Return the object elements of a nested list."""
        value = self._data.get(key)
        if not isinstance(value, list):
            return []
        return [Fields(item) for item in value if isinstance(item, dict)]

    def numbers(self, key: str) -> list[float]:
        """Return the numeric elements of a nested list."""
        value = self._data.get(key)
        if not isinstance(value, list):
            return []
        return [float(v) for v in value if isinstance(v, int | float) and not isinstance(v, bool)]

    def strings(self, key: str) -> list[str]:
        """Return the string elements of a nested list."""
        value = self._data.get(key)
        return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []

    def timestamp(self, key: str) -> datetime | None:
        """Return an aware datetime from a decoded date, ISO-8601, or Rouvy display string."""
        value = self._data.get(key)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return self._display_timestamp(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _display_timestamp(value: str) -> datetime | None:
        """Parse the display format Rouvy uses in some payloads: ``Sep 28, 2026, 12:00 AM UTC``."""
        try:
            parsed = datetime.strptime(value, _DISPLAY_FORMAT)  # noqa: DTZ007 - suffix is always UTC
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC)

    def day(self, key: str) -> date | None:
        """Return a calendar date from a decoded date or an ISO-8601 string."""
        value = self._data.get(key)
        if isinstance(value, str) and len(value) == len("YYYY-MM-DD"):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        stamp = self.timestamp(key)
        return stamp.date() if stamp else None


class Payload:
    """A decoded single-fetch response with helpers to locate data inside it."""

    def __init__(self, root: TurboValue) -> None:
        self._root = root

    @classmethod
    def parse(cls, text: str) -> Payload:
        """Decode a turbo-stream body.

        Raises:
            RouvyResponseError: If the body is not valid turbo-stream.
        """
        return cls(TurboStreamDecoder().decode(text))

    @property
    def root(self) -> TurboValue:
        """Return the decoded root value."""
        return self._root

    @property
    def redirect_location(self) -> str | None:
        """Return the target of a single-fetch redirect response, if this is one."""
        target: TurboValue = self._root
        if isinstance(target, TaggedValue) and target.tag == _REDIRECT_TAG and target.args:
            target = target.args[0]
        fields = Fields.wrap(target)
        if fields is None or not fields.has("status"):
            return None
        return fields.text("redirect")

    @property
    def action_data(self) -> Fields | None:
        """Return the ``data`` object of an action (form POST) response."""
        root = Fields.wrap(self._root)
        return root.mapping("data") if root else None

    def find(self, key: str) -> TurboValue:
        """Return the value of the shallowest occurrence of ``key`` (breadth-first)."""
        return next(self._search(key), None)

    def find_fields(self, key: str) -> Fields | None:
        """Return the shallowest object stored under ``key``."""
        return next((Fields(v) for v in self._search(key) if isinstance(v, dict)), None)

    def find_records(self, key: str) -> list[Fields] | None:
        """Return the shallowest list stored under ``key`` as objects, or None if absent."""
        for value in self._search(key):
            if isinstance(value, list):
                return [Fields(item) for item in value if isinstance(item, dict)]
        return None

    def objects_with(self, key: str) -> Iterator[Fields]:
        """Yield every object (breadth-first) that contains ``key``."""
        for node in self._walk():
            if isinstance(node, dict) and key in node:
                yield Fields(node)

    # Internals

    def _search(self, key: str) -> Iterator[TurboValue]:
        """Yield values stored under ``key`` in breadth-first order."""
        for node in self._walk():
            if isinstance(node, dict) and key in node:
                yield node[key]

    def _walk(self) -> Iterator[TurboValue]:
        """Yield every container node once, breadth-first, tolerating cycles."""
        queue: deque[TurboValue] = deque([self._root])
        seen: set[int] = set()
        while queue:
            node = queue.popleft()
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node
            if isinstance(node, dict):
                queue.extend(v for v in node.values() if isinstance(v, dict | list))
            elif isinstance(node, list):
                queue.extend(v for v in node if isinstance(v, dict | list))
