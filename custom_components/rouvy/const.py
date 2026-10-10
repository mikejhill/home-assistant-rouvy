"""Constants for the Rouvy integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

DOMAIN: Final = "rouvy"
LOGGER: Final = logging.getLogger(__package__)

CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"

UPDATE_INTERVAL: Final = timedelta(hours=1)
MAX_CONCURRENT_REQUESTS: Final = 4
