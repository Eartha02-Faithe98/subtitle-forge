from pathlib import Path

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
    assert settings.data_root == Path(__file__).parents[2] / "runtime" / "data" / "jobs"
    assert settings.upload_max_bytes == 1_073_741_824
    assert settings.ffprobe_timeout_seconds == 30
    assert settings.ffmpeg_timeout_seconds == 600
    assert settings.youtube_timeout_seconds == 900
    assert settings.whisper_models == {
        "fast": "base.en",
        "balanced": "small.en",
        "accurate": "medium.en",
    }
    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"
    assert settings.audio_chunk_seconds == 900
    assert settings.audio_chunk_overlap_seconds == 5
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_model == "qwen2.5:7b"
    assert settings.ollama_timeout_seconds == 180
    assert settings.prompt_max_chars == 12_000
    assert settings.poll_interval_ms == 1_000
    assert settings.retention_hours == 168


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


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SUBTITLE_FORGE_DATA_ROOT", "relative/path"),
        ("SUBTITLE_FORGE_UPLOAD_MAX_BYTES", "0"),
        ("SUBTITLE_FORGE_FFPROBE_TIMEOUT_SECONDS", "0"),
        ("SUBTITLE_FORGE_FFMPEG_TIMEOUT_SECONDS", "0"),
        ("SUBTITLE_FORGE_YOUTUBE_TIMEOUT_SECONDS", "0"),
        ("SUBTITLE_FORGE_OLLAMA_BASE_URL", "http://user:secret@localhost:11434"),
        ("SUBTITLE_FORGE_OLLAMA_BASE_URL", "http://localhost:11434/api"),
        ("SUBTITLE_FORGE_OLLAMA_MODEL", " "),
        ("SUBTITLE_FORGE_PROMPT_MAX_CHARS", "0"),
        ("SUBTITLE_FORGE_POLL_INTERVAL_MS", "99"),
        ("SUBTITLE_FORGE_RETENTION_HOURS", "0"),
    ],
)
def test_settings_reject_unsafe_phase_one_overrides(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_require_all_whisper_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SUBTITLE_FORGE_WHISPER_MODELS",
        '{"fast":"tiny.en","balanced":"base.en"}',
    )

    with pytest.raises(ValidationError, match="fast, balanced, and accurate"):
        Settings(_env_file=None)


def test_settings_reject_chunk_overlap_that_consumes_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUBTITLE_FORGE_AUDIO_CHUNK_SECONDS", "30")
    monkeypatch.setenv("SUBTITLE_FORGE_AUDIO_CHUNK_OVERLAP_SECONDS", "30")

    with pytest.raises(ValidationError, match="overlap"):
        Settings(_env_file=None)
