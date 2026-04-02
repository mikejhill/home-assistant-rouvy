"""Tests for the RouvyConfig dataclass."""

import pytest

from rouvy_api_client.config import RouvyConfig


class TestRouvyConfig:
    """Verify configuration dataclass behavior."""

    def test_required_fields_stored(self) -> None:
        config = RouvyConfig(email="user@test.com", password="secret")
        assert config.email == "user@test.com", (
            f"Expected email 'user@test.com', got {config.email}"
        )
        assert config.password == "secret", f"Expected password 'secret', got {config.password}"

    def test_default_timeout(self) -> None:
        config = RouvyConfig(email="a@b.com", password="p")
        assert config.timeout_seconds == 30.0, (
            f"Expected default timeout 30.0, got {config.timeout_seconds}"
        )

    def test_custom_timeout(self) -> None:
        config = RouvyConfig(email="a@b.com", password="p", timeout_seconds=10.0)
        assert config.timeout_seconds == 10.0, (
            f"Expected custom timeout 10.0, got {config.timeout_seconds}"
        )

    def test_frozen_cannot_modify_email(self) -> None:
        config = RouvyConfig(email="a@b.com", password="p")
        with pytest.raises(AttributeError, match="cannot assign"):
            config.email = "new@b.com"  # type: ignore[misc]

    def test_frozen_cannot_modify_password(self) -> None:
        config = RouvyConfig(email="a@b.com", password="p")
        with pytest.raises(AttributeError, match="cannot assign"):
            config.password = "new"  # type: ignore[misc]

    def test_frozen_cannot_modify_timeout(self) -> None:
        config = RouvyConfig(email="a@b.com", password="p")
        with pytest.raises(AttributeError, match="cannot assign"):
            config.timeout_seconds = 99.0  # type: ignore[misc]
