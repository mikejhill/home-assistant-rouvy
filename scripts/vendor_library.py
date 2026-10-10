# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Copy src/rouvy_api into the Home Assistant integration, or check the copy is current.

HACS installs only ``custom_components/rouvy``, so the integration ships its own copy
of the library. Imports are rewritten to ``custom_components.rouvy.rouvy_api``.

Usage: uv run scripts/vendor_library.py [--check]
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
SOURCE: Final = ROOT / "src" / "rouvy_api"
TARGET: Final = ROOT / "custom_components" / "rouvy" / "rouvy_api"
EXCLUDED: Final = frozenset({"cli", "__pycache__"})
IMPORT_PATTERN: Final = re.compile(r"^(\s*)(from|import) rouvy_api(\.|\s)", re.MULTILINE)
VENDORED_PACKAGE: Final = "custom_components.rouvy.rouvy_api"


class LibraryVendor:
    """Render and compare the vendored copy of the library."""

    def render(self) -> dict[Path, str]:
        """Return relative path -> rewritten content for every vendored file."""
        files: dict[Path, str] = {}
        for path in sorted(SOURCE.rglob("*")):
            relative = path.relative_to(SOURCE)
            if path.is_dir() or EXCLUDED.intersection(relative.parts):
                continue
            text = path.read_text(encoding="utf-8")
            files[relative] = IMPORT_PATTERN.sub(rf"\1\2 {VENDORED_PACKAGE}\3", text)
        return files

    def write(self) -> None:
        """Replace the vendored copy."""
        if TARGET.exists():
            shutil.rmtree(TARGET)
        for relative, text in self.render().items():
            destination = TARGET / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8", newline="\n")

    def stale_files(self) -> list[str]:
        """Return paths that differ between the source and the vendored copy."""
        expected = self.render()
        actual = (
            {
                p.relative_to(TARGET): p.read_text(encoding="utf-8")
                for p in TARGET.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            }
            if TARGET.exists()
            else {}
        )
        names = set(expected) | set(actual)
        return sorted(str(n) for n in names if expected.get(n) != actual.get(n))


class Application:
    """Command-line entry point."""

    @classmethod
    def main(cls) -> None:
        """Vendor the library, or verify it with --check."""
        vendor = LibraryVendor()
        if "--check" not in sys.argv[1:]:
            vendor.write()
            sys.stdout.write(f"Vendored rouvy_api into {TARGET.relative_to(ROOT)}\n")
            return
        stale = vendor.stale_files()
        if stale:
            sys.stderr.write("Vendored library is stale; run `uv run poe vendor`:\n")
            sys.stderr.write("".join(f"  {name}\n" for name in stale))
            sys.exit(1)
        sys.stdout.write("Vendored library is up to date\n")


if __name__ == "__main__":
    Application.main()
