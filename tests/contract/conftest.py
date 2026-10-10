"""Fixtures for live, unauthenticated contract tests against rouvy.com."""

from __future__ import annotations

import pytest

from tests.support.network import RealNetwork


@pytest.fixture(autouse=True)
def real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow real outbound connections."""
    RealNetwork.enable(monkeypatch)
