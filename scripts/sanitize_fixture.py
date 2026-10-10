# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Strip personal data from a captured Rouvy turbo-stream response so it can be committed.

Usage: uv run scripts/sanitize_fixture.py <captured.txt> <output.txt>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

type Flat = bool | int | float | str | list[Flat] | dict[str, Flat] | None

SENSITIVE_KEYS: Final = frozenset(
    {
        "email",
        "userName",
        "username",
        "currentUsername",
        "firebaseUid",
        "userId",
        "uid",
        "firstName",
        "lastName",
        "avatarUrl",
        "avatar",
        "team",
        "redirectUrl",
    }
)
SECRET_CONTAINER_KEYS: Final = frozenset({"ENV", "requestInfo", "notificationsPromise"})
MEDIA_MARKERS: Final = ("firebasestorage", "token=", "activity_media", "/o/")
MIN_TOKEN_LENGTH: Final = 6  # shorter values are too generic to scrub inside other strings
BIRTH_DATE_MS: Final = 631152000000  # 1990-01-01T00:00:00Z
PLACEHOLDERS: Final = {
    "email": "rider@example.com",
    "userName": "test-rider",
    "username": "test-rider",
    "currentUsername": "test-rider",
}


class FixtureSanitizer:
    """Replace personal strings in every line of a turbo-stream body."""

    def __init__(self, text: str) -> None:
        self._lines = [
            json.loads(line.partition(":")[2]) if i else json.loads(line)
            for i, line in enumerate(text.strip().splitlines())
        ]
        self._prefixes = [line.partition(":")[0] for line in text.strip().splitlines()]
        self._values: list[Flat] = []
        for chunk in self._lines:
            if isinstance(chunk, list):
                self._values.extend(chunk)

    def sanitize(self) -> str:
        """Return the sanitized body."""
        replacements = self._replacements()
        tokens = [v for v in replacements if len(v) >= MIN_TOKEN_LENGTH]
        cleaned: list[Flat] = [
            self._scrub(value, replacements, tokens) if isinstance(value, str) else value
            for value in self._values
        ]
        for index in self._birth_dates():
            cleaned[index] = ["D", BIRTH_DATE_MS]
        return self._render(cleaned)

    # Internals

    def _replacements(self) -> dict[str, str]:
        """Map each sensitive string to its placeholder."""
        found: dict[str, str] = {}
        for key, value_index in self._entries():
            if key in SENSITIVE_KEYS:
                self._mark(value_index, found, PLACEHOLDERS.get(key, "redacted"))
            elif key in SECRET_CONTAINER_KEYS:
                self._mark_container(value_index, found)
        return found

    def _entries(self) -> list[tuple[str, int]]:
        """Return (key, value index) for every object entry."""
        entries: list[tuple[str, int]] = []
        for value in self._values:
            if not isinstance(value, dict):
                continue
            for encoded_key, value_index in value.items():
                key = self._at(int(encoded_key[1:]))
                if isinstance(key, str) and isinstance(value_index, int):
                    entries.append((key, value_index))
        return entries

    def _mark(self, index: int, found: dict[str, str], placeholder: str = "redacted") -> None:
        """Record a sensitive string value."""
        value = self._at(index)
        if isinstance(value, str) and value:
            found.setdefault(value, placeholder)

    def _mark_container(self, index: int, found: dict[str, str]) -> None:
        """Record every string inside a secret container."""
        value = self._at(index)
        if isinstance(value, dict):
            for item in value.values():
                if isinstance(item, int):
                    self._mark(item, found)
                    self._mark_container(item, found)

    def _birth_dates(self) -> list[int]:
        """Return indices of birth date values."""
        return [
            i for key, i in self._entries() if key == "birthDate" and isinstance(self._at(i), list)
        ]

    def _at(self, index: int) -> Flat:
        """Return the raw value at an index, or None for sentinels."""
        return self._values[index] if 0 <= index < len(self._values) else None

    @staticmethod
    def _scrub(value: str, replacements: dict[str, str], tokens: list[str]) -> str:
        """Replace a sensitive string or any sensitive token inside it."""
        if value in replacements:
            return replacements[value]
        if value.startswith("http") and any(m in value for m in MEDIA_MARKERS):
            return "https://example.invalid/media.jpg"
        for token in tokens:
            if token in value:
                value = value.replace(token, "redacted")
        return value

    def _render(self, cleaned: list[Flat]) -> str:
        """Re-split values into the original lines."""
        out: list[str] = []
        offset = 0
        for prefix, chunk in zip(self._prefixes, self._lines, strict=True):
            if isinstance(chunk, list):
                body = json.dumps(cleaned[offset : offset + len(chunk)], separators=(",", ":"))
                offset += len(chunk)
            else:
                body = json.dumps(chunk)
            out.append(body if prefix == self._prefixes[0] and not out else f"{prefix}:{body}")
        return "\n".join(out) + "\n"


class Application:
    """Command-line entry point."""

    @classmethod
    def main(cls) -> None:
        """Sanitize argv[1] into argv[2]."""
        source, target = Path(sys.argv[1]), Path(sys.argv[2])
        sanitized = FixtureSanitizer(source.read_text(encoding="utf-8")).sanitize()
        target.write_text(sanitized, encoding="utf-8")
        sys.stdout.write(f"Wrote {target}\n")


if __name__ == "__main__":
    Application.main()
