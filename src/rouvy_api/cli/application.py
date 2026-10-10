"""Entry point of the rouvy-api command-line interface."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

from dotenv import load_dotenv

from rouvy_api.cli.command_line import CommandLine
from rouvy_api.cli.commands import HANDLERS
from rouvy_api.cli.output import OutputWriter
from rouvy_api.cli.settings import GlobalSettings, RunSettings
from rouvy_api.client import RouvyClient
from rouvy_api.config import DEFAULT_BASE_URL, ClientConfig, Credentials
from rouvy_api.exceptions import RouvyError

logger = logging.getLogger(__name__)

EXIT_OK: Final = 0
EXIT_ERROR: Final = 1
EXIT_INTERRUPTED: Final = 130


class CliError(RouvyError):
    """A user-facing configuration problem detected by the CLI."""


@dataclass(frozen=True, slots=True)
class Environment:
    """Credentials and connection settings resolved from options and environment."""

    credentials: Credentials
    config: ClientConfig

    @classmethod
    def resolve(cls, options: GlobalSettings) -> Environment:
        """Load the env file and build credentials and client config.

        Raises:
            CliError: If credentials are missing or invalid.
        """
        env_file = options.env_file or Path(".env")
        if env_file.is_file():
            load_dotenv(env_file, override=False)
        elif options.env_file is not None:
            msg = f"Env file not found: {env_file}"
            raise CliError(msg)
        email = options.email or os.environ.get("ROUVY_EMAIL", "")
        password = os.environ.get("ROUVY_PASSWORD", "")
        if not email or not password:
            msg = "Set ROUVY_EMAIL and ROUVY_PASSWORD (environment or .env file)"
            raise CliError(msg)
        try:
            credentials = Credentials(email, password)
            config = ClientConfig(
                base_url=options.base_url or os.environ.get("ROUVY_BASE_URL") or DEFAULT_BASE_URL,
                timeout_s=options.timeout_s,
            )
        except ValueError as err:
            raise CliError(str(err)) from err
        return cls(credentials, config)


class Application:
    """The rouvy-api program."""

    def __init__(self, stdout: TextIO | None = None, stderr: TextIO | None = None) -> None:
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    @classmethod
    def main(cls) -> None:
        """Run with sys.argv and exit with the resulting status."""
        cls.tolerate_unencodable_output()
        sys.exit(cls().run())

    @staticmethod
    def tolerate_unencodable_output() -> None:
        """Replace characters the console cannot show (e.g. emoji on cp1252) instead of crashing."""
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, io.TextIOWrapper):
                stream.reconfigure(errors="replace")

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Parse arguments, run the command, and return an exit status."""
        settings = CommandLine().parse(argv)
        logging.basicConfig(
            level=settings.options.log_level,
            stream=self._stderr,
            format="%(levelname)s %(name)s: %(message)s",
        )
        try:
            return asyncio.run(self.execute(settings))
        except KeyboardInterrupt:
            self._stderr.write("interrupted\n")
            return EXIT_INTERRUPTED

    async def execute(self, settings: RunSettings) -> int:
        """Run one parsed command and return an exit status."""
        try:
            environment = Environment.resolve(settings.options)
            async with RouvyClient.open(
                environment.credentials, config=environment.config
            ) as client:
                report = await HANDLERS[settings.command](client, settings.args)
        except RouvyError as err:
            logger.debug("Command failed", exc_info=err)
            self._stderr.write(f"error: {err}\n")
            return EXIT_ERROR
        OutputWriter(self._stdout, as_json=settings.options.json_output).write(report)
        return EXIT_OK
