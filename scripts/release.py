# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Prepare a release: bump every version string and move Unreleased changelog notes.

Usage:
    uv run scripts/release.py prepare 2.1.0     # edit files in place
    uv run scripts/release.py notes 2.1.0       # print that version's changelog section
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
VERSION_PATTERN: Final = re.compile(r"^\d+\.\d+\.\d+$")
UNRELEASED: Final = "## [Unreleased]"


class ReleaseError(Exception):
    """A release precondition failed."""


@dataclass(frozen=True, slots=True)
class ReleaseFiles:
    """Paths of every file that carries the version."""

    root: Path

    @property
    def pyproject(self) -> Path:
        """pyproject.toml."""
        return self.root / "pyproject.toml"

    @property
    def library_version(self) -> Path:
        """src/rouvy_api/_version.py."""
        return self.root / "src" / "rouvy_api" / "_version.py"

    @property
    def manifest(self) -> Path:
        """The integration manifest."""
        return self.root / "custom_components" / "rouvy" / "manifest.json"

    @property
    def changelog(self) -> Path:
        """CHANGELOG.md."""
        return self.root / "CHANGELOG.md"


class ReleasePreparer:
    """Apply a version bump and changelog promotion to a checkout."""

    def __init__(self, files: ReleaseFiles, version: str, *, today: str | None = None) -> None:
        if not VERSION_PATTERN.fullmatch(version):
            msg = f"Version must look like 1.2.3, got {version!r}"
            raise ReleaseError(msg)
        self._files = files
        self._version = version
        self._today = today or datetime.now(UTC).date().isoformat()

    def prepare(self) -> None:
        """Bump versions and promote the Unreleased changelog section."""
        changelog = self._promote_changelog(self._files.changelog.read_text(encoding="utf-8"))
        self._replace(
            self._files.pyproject, r'(?m)^version = "[^"]+"', f'version = "{self._version}"'
        )
        self._replace(
            self._files.library_version,
            r'__version__: Final = "[^"]+"',
            f'__version__: Final = "{self._version}"',
        )
        manifest = json.loads(self._files.manifest.read_text(encoding="utf-8"))
        manifest["version"] = self._version
        self._files.manifest.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        self._files.changelog.write_text(changelog, encoding="utf-8", newline="\n")

    def notes(self) -> str:
        """Return the changelog section of this version."""
        text = self._files.changelog.read_text(encoding="utf-8")
        match = re.search(
            rf"^## \[{re.escape(self._version)}\][^\n]*\n(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if match is None:
            msg = f"CHANGELOG.md has no section for {self._version}"
            raise ReleaseError(msg)
        return match.group(1).strip() + "\n"

    # Internals

    def _promote_changelog(self, text: str) -> str:
        """Turn the Unreleased notes into a dated version section."""
        if f"## [{self._version}]" in text:
            msg = f"CHANGELOG.md already has a section for {self._version}"
            raise ReleaseError(msg)
        start = text.find(UNRELEASED)
        if start < 0:
            msg = "CHANGELOG.md has no [Unreleased] section"
            raise ReleaseError(msg)
        body_start = start + len(UNRELEASED)
        next_section = text.find("\n## ", body_start)
        body = text[body_start : next_section if next_section >= 0 else len(text)]
        if not body.strip():
            msg = "The [Unreleased] section is empty; describe the changes first"
            raise ReleaseError(msg)
        header = f"{UNRELEASED}\n\n## [{self._version}] - {self._today}"
        return text[:start] + header + text[body_start:]

    @staticmethod
    def _replace(path: Path, pattern: str, replacement: str) -> None:
        """Replace exactly one version string in a file."""
        text = path.read_text(encoding="utf-8")
        updated, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            msg = f"Could not find the version in {path.name}"
            raise ReleaseError(msg)
        path.write_text(updated, encoding="utf-8", newline="\n")


class Application:
    """Command-line entry point."""

    @classmethod
    def main(cls) -> None:
        """Run 'prepare' or 'notes' for a version."""
        if len(sys.argv) != 3 or sys.argv[1] not in {"prepare", "notes"}:  # noqa: PLR2004
            sys.stderr.write(__doc__ or "")
            sys.exit(2)
        command, version = sys.argv[1], sys.argv[2]
        try:
            preparer = ReleasePreparer(ReleaseFiles(ROOT), version)
            if command == "prepare":
                preparer.prepare()
                sys.stdout.write(f"Prepared release {version}\n")
            else:
                sys.stdout.write(preparer.notes())
        except ReleaseError as err:
            sys.stderr.write(f"error: {err}\n")
            sys.exit(1)


if __name__ == "__main__":
    Application.main()
