"""Safe startup readiness checks for local Phase 1 dependencies."""

import shutil
from collections.abc import Callable
from pathlib import Path

import httpx
from huggingface_hub import scan_cache_dir

from subtitle_forge_api.settings import Settings


def _whisper_model_is_local(model_name: str) -> bool:
    model_path = Path(model_name)
    if model_path.is_absolute() and model_path.is_dir():
        return True

    repository_id = f"Systran/faster-whisper-{model_name}"
    try:
        return any(repo.repo_id == repository_id for repo in scan_cache_dir().repos)
    except Exception:
        return False


def _ollama_is_available(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=1.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def check_readiness(
    settings: Settings,
    *,
    executable_locator: Callable[[str], str | None] = shutil.which,
    whisper_model_locator: Callable[[str], bool] = _whisper_model_is_local,
    ollama_probe: Callable[[str], bool] = _ollama_is_available,
) -> dict[str, object]:
    """Return cached-at-startup dependency guidance without exposing local paths."""
    selected_model = settings.whisper_models["balanced"]
    availability = {
        "ffmpeg": executable_locator("ffmpeg") is not None,
        "ffprobe": executable_locator("ffprobe") is not None,
        "whisper_model": whisper_model_locator(selected_model),
        "ollama": ollama_probe(settings.ollama_base_url),
    }
    guidance = {
        "ffmpeg": "Install FFmpeg and make ffmpeg available on PATH.",
        "ffprobe": "Install FFmpeg and make ffprobe available on PATH.",
        "whisper_model": "Prepare the selected Local Whisper model before processing.",
        "ollama": "Start the configured Ollama-compatible service and prepare its model.",
    }
    dependencies = {
        name: {
            "available": available,
            "message": "Available" if available else guidance[name],
        }
        for name, available in availability.items()
    }
    return {
        "status": "ready" if all(availability.values()) else "needs_setup",
        "dependencies": dependencies,
    }
