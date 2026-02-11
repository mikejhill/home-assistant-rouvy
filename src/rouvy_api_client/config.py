from dataclasses import dataclass


@dataclass(frozen=True)
class RouvyConfig:
    email: str
    password: str
    timeout_seconds: float = 30.0
