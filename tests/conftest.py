"""Pytest configuration for the home-assistant-rouvy test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-deselect integration tests unless ``-m integration`` is passed."""
    marker_expr = config.getoption("-m", default="")
    if "integration" in str(marker_expr):
        return

    skip = __import__("pytest").mark.skip(reason="integration tests not selected")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
