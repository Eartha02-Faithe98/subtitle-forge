import pytest
from pydantic import ValidationError

from subtitle_forge_api.settings import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.environment == "development"
    assert settings.allowed_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_settings_accept_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUBTITLE_FORGE_HOST", "0.0.0.0")
    monkeypatch.setenv("SUBTITLE_FORGE_PORT", "8100")
    monkeypatch.setenv("SUBTITLE_FORGE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SUBTITLE_FORGE_ALLOWED_ORIGINS",
        '["http://localhost:3100"]',
    )

    settings = Settings(_env_file=None)

    assert settings.host == "0.0.0.0"
    assert settings.port == 8100
    assert settings.environment == "test"
    assert settings.allowed_origins == ["http://localhost:3100"]


@pytest.mark.parametrize("port", ["0", "70000", "not-a-port"])
def test_settings_reject_invalid_ports(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    monkeypatch.setenv("SUBTITLE_FORGE_PORT", port)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_wildcard_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUBTITLE_FORGE_ALLOWED_ORIGINS", '["*"]')

    with pytest.raises(ValidationError, match="wildcard"):
        Settings(_env_file=None)
