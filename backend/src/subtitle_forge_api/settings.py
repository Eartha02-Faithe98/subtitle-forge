"""Centralized, validated application settings."""

from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import Field, StringConstraints, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local env file."""

    model_config = SettingsConfigDict(
        env_prefix="SUBTITLE_FORGE_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    host: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    environment: Literal["development", "test", "production"] = "development"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    data_root: Path = PROJECT_ROOT / "runtime" / "data" / "jobs"
    upload_max_bytes: int = Field(default=1_073_741_824, ge=1)
    ffprobe_timeout_seconds: int = Field(default=30, ge=1, le=300)
    ffmpeg_timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    youtube_timeout_seconds: int = Field(default=900, ge=1, le=86_400)
    whisper_models: dict[str, str] = Field(
        default_factory=lambda: {
            "fast": "base.en",
            "balanced": "small.en",
            "accurate": "medium.en",
        }
    )
    whisper_device: Literal["cpu", "cuda", "auto"] = "cpu"
    whisper_compute_type: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ] = "int8"
    audio_chunk_seconds: int = Field(default=900, ge=30, le=7_200)
    audio_chunk_overlap_seconds: int = Field(default=5, ge=0, le=300)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ] = "qwen2.5:7b"
    ollama_timeout_seconds: int = Field(default=180, ge=1, le=3_600)
    prompt_max_chars: int = Field(default=12_000, ge=1_000, le=1_000_000)
    poll_interval_ms: int = Field(default=1_000, ge=100, le=60_000)
    retention_hours: int = Field(default=168, ge=1, le=8_760)

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, origins: list[str]) -> list[str]:
        """Require explicit HTTP(S) origins without credentials or path components."""
        validated: list[str] = []
        for origin in origins:
            if origin == "*":
                raise ValueError("wildcard origins are not allowed")

            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError("origins must be explicit HTTP(S) origins")

            validated.append(origin.rstrip("/"))

        if not validated:
            raise ValueError("at least one allowed origin is required")
        return validated

    @field_validator("data_root")
    @classmethod
    def validate_data_root(cls, value: Path) -> Path:
        """Require a dedicated absolute directory instead of an ambiguous relative path."""
        if not value.is_absolute() or value == Path(value.anchor):
            raise ValueError("data root must be a dedicated absolute path")
        return value

    @field_validator("whisper_models")
    @classmethod
    def validate_whisper_models(cls, models: dict[str, str]) -> dict[str, str]:
        """Require one non-empty model identifier for every UI performance profile."""
        if set(models) != {"fast", "balanced", "accurate"}:
            raise ValueError("whisper models must define fast, balanced, and accurate")
        if any(not model.strip() for model in models.values()):
            raise ValueError("whisper model identifiers cannot be empty")
        return {profile: model.strip() for profile, model in models.items()}

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        """Accept an explicit HTTP(S) origin without credentials or API paths."""
        parsed = urlparse(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Ollama base URL must be an explicit HTTP(S) origin")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> Self:
        """Keep overlap smaller than the audio chunk it overlaps."""
        if self.audio_chunk_overlap_seconds >= self.audio_chunk_seconds:
            raise ValueError("audio chunk overlap must be smaller than the chunk")
        return self
