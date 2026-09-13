import re
import tomllib
from pathlib import Path


def test_phase_one_runtime_dependencies_are_declared() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]
    dependencies = project["dependencies"]

    assert "python-multipart>=0.0.32,<1" in dependencies
    assert "yt-dlp>=2026.8.19,<2027" in dependencies
    assert "faster-whisper>=1.2.1,<2" in dependencies
    assert "httpx>=0.28.1,<1" in dependencies
    assert "numpy>=1.23,<2.5" in dependencies


def test_phase_one_environment_example_contains_only_non_secret_settings() -> None:
    example_path = Path(__file__).parents[2] / ".env.example"
    assignments = {
        line.partition("=")[0]: line.partition("=")[2]
        for line in example_path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    expected_phase_one_names = {
        "SUBTITLE_FORGE_DATA_ROOT",
        "SUBTITLE_FORGE_UPLOAD_MAX_BYTES",
        "SUBTITLE_FORGE_FFPROBE_TIMEOUT_SECONDS",
        "SUBTITLE_FORGE_FFMPEG_TIMEOUT_SECONDS",
        "SUBTITLE_FORGE_YOUTUBE_TIMEOUT_SECONDS",
        "SUBTITLE_FORGE_WHISPER_MODELS",
        "SUBTITLE_FORGE_WHISPER_DEVICE",
        "SUBTITLE_FORGE_WHISPER_COMPUTE_TYPE",
        "SUBTITLE_FORGE_AUDIO_CHUNK_SECONDS",
        "SUBTITLE_FORGE_AUDIO_CHUNK_OVERLAP_SECONDS",
        "SUBTITLE_FORGE_OLLAMA_BASE_URL",
        "SUBTITLE_FORGE_OLLAMA_MODEL",
        "SUBTITLE_FORGE_OLLAMA_TIMEOUT_SECONDS",
        "SUBTITLE_FORGE_PROMPT_MAX_CHARS",
        "SUBTITLE_FORGE_POLL_INTERVAL_MS",
        "SUBTITLE_FORGE_RETENTION_HOURS",
    }

    assert expected_phase_one_names <= assignments.keys()
    assert {name for name in assignments if name.startswith("NEXT_PUBLIC_")} == {
        "NEXT_PUBLIC_API_BASE_URL"
    }
    assert not {
        name
        for name in assignments
        if re.search(r"(?:API_?KEY|TOKEN|PASSWORD|SECRET|CREDENTIAL)", name, re.IGNORECASE)
    }
    assert all(value.strip() for value in assignments.values())
