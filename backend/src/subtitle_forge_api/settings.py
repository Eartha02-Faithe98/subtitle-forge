"""Centralized, validated application settings."""

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, StringConstraints, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
