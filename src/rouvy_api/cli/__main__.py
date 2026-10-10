"""Allow ``python -m rouvy_api.cli``."""

from __future__ import annotations

from rouvy_api.cli.application import Application

if __name__ == "__main__":
    Application.main()
