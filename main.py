#!/usr/bin/env python3
"""
Rouvy API client - Command-line interface wrapper.

This is a convenience wrapper for running the CLI directly.
The main CLI implementation is in src/rouvy_api_client/__main__.py

You can also run the CLI using:
    python -m rouvy_api_client
"""

import sys
from pathlib import Path

# Add src/ to Python path so imports work
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rouvy_api_client.__main__ import main

if __name__ == "__main__":
    main()
