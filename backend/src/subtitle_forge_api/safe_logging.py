"""Minimal structured operational logs without raw user or provider data."""

import logging
from uuid import UUID

from subtitle_forge_api.domain import JobStage
from subtitle_forge_api.errors import classify_error

_KNOWN_PROVIDERS = {
    "ffmpeg",
    "ffprobe",
    "local_whisper",
    "ollama",
    "pipeline",
    "yt_dlp",
}


class JobEventLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def record(
        self,
        *,
        job_id: str,
        stage: JobStage,
        provider: str,
        duration_ms: int,
        error: Exception | None = None,
    ) -> None:
        self._logger.info(
            "subtitle_forge_job_event",
            extra={
                "job_id": _safe_job_id(job_id),
                "stage": stage.value,
                "provider": (provider if provider in _KNOWN_PROVIDERS else "unknown"),
                "duration_ms": max(0, duration_ms),
                "error_category": (classify_error(error).value if error is not None else None),
            },
        )


def _safe_job_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError:
        return "invalid"
    return value if str(parsed) == value else "invalid"
