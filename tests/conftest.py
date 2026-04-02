"""Pytest configuration for the rouvy-api-client test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so custom_components can be imported in tests.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
