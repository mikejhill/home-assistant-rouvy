"""Tests for the release preparation script."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


class ReleaseModule:
    """Load scripts/release.py, which is not part of the installed package."""

    @staticmethod
    def load() -> ModuleType:
        """Import the script as a module."""
        spec = importlib.util.spec_from_file_location(
            "release_script", ROOT / "scripts" / "release.py"
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
        return module


@pytest.fixture
def release() -> ModuleType:
    """The release script module."""
    return ReleaseModule.load()


SAMPLE_CHANGELOG = """# Changelog

## [Unreleased]

### Fixed

- Login works again.

## [1.0.0] - 2026-01-01

- First release.
"""


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """Copies of the version-bearing files plus a changelog with pending notes.

    The real CHANGELOG is not used: during a release its [Unreleased] section is
    already promoted (empty) when the test suite runs.
    """
    for relative in (
        "pyproject.toml",
        "src/rouvy_api/_version.py",
        "custom_components/rouvy/manifest.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    (tmp_path / "CHANGELOG.md").write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    return tmp_path


class TestPrepare:
    """Version bumps and changelog promotion."""

    def test_bumps_every_version(self, release: ModuleType, checkout: Path) -> None:
        """pyproject, the library, and the manifest all get the new version."""
        files = release.ReleaseFiles(checkout)

        release.ReleasePreparer(files, "9.8.7", today="2030-01-02").prepare()

        assert 'version = "9.8.7"' in files.pyproject.read_text(encoding="utf-8")
        assert '__version__: Final = "9.8.7"' in files.library_version.read_text(encoding="utf-8")
        assert json.loads(files.manifest.read_text(encoding="utf-8"))["version"] == "9.8.7"

    def test_promotes_unreleased_notes(self, release: ModuleType, checkout: Path) -> None:
        """Unreleased notes move under a dated heading and a fresh Unreleased section remains."""
        files = release.ReleaseFiles(checkout)
        preparer = release.ReleasePreparer(files, "9.8.7", today="2030-01-02")

        preparer.prepare()

        text = files.changelog.read_text(encoding="utf-8")
        assert "## [Unreleased]\n\n## [9.8.7] - 2030-01-02" in text
        assert "Login works again" in preparer.notes()

    @pytest.mark.parametrize("version", ["2.0", "v2.0.0", "2.0.0-rc1", ""])
    def test_rejects_bad_versions(self, release: ModuleType, checkout: Path, version: str) -> None:
        """Only plain semantic versions are accepted."""
        with pytest.raises(release.ReleaseError, match=r"1.2.3"):
            release.ReleasePreparer(release.ReleaseFiles(checkout), version)

    def test_rejects_empty_unreleased(self, release: ModuleType, checkout: Path) -> None:
        """Releasing with nothing under Unreleased fails."""
        files = release.ReleaseFiles(checkout)
        release.ReleasePreparer(files, "9.8.7").prepare()

        with pytest.raises(release.ReleaseError, match="empty"):
            release.ReleasePreparer(files, "9.8.8").prepare()

    def test_rejects_duplicate_version(self, release: ModuleType, checkout: Path) -> None:
        """A version that already has a section cannot be released again."""
        files = release.ReleaseFiles(checkout)
        release.ReleasePreparer(files, "9.8.7").prepare()

        with pytest.raises(release.ReleaseError, match="already"):
            release.ReleasePreparer(files, "9.8.7").prepare()

    def test_missing_notes(self, release: ModuleType, checkout: Path) -> None:
        """Notes for an unknown version are an error."""
        with pytest.raises(release.ReleaseError, match="no section"):
            release.ReleasePreparer(release.ReleaseFiles(checkout), "9.9.9").notes()

    def test_repository_is_releasable(self, release: ModuleType) -> None:
        """The real CHANGELOG has Unreleased notes or a section for the current version."""
        files = release.ReleaseFiles(ROOT)
        version = json.loads(files.manifest.read_text(encoding="utf-8"))["version"]
        text = files.changelog.read_text(encoding="utf-8")

        assert "## [Unreleased]" in text
        assert (
            f"## [{version}]" in text
            or "### " in text.split("## [Unreleased]", 1)[1].split("\n## ", 1)[0]
        )
