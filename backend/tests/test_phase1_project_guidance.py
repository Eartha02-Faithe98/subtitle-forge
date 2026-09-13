from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_readme_describes_phase_one_without_claiming_future_features() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        "Phase 1 Local Web UI MVP",
        "FFmpeg",
        "Local faster-whisper",
        "Ollama-compatible",
        "YouTube",
        "MP3",
        "MP4",
        "transcript-en.txt",
        "transcript-zh-TW.txt",
        "subtitles-en.srt",
        "subtitles-zh-TW.srt",
        "subtitles-bilingual.srt",
        "summary-en.md",
        "summary-zh-TW.md",
        "Storage",
        "Troubleshooting",
        "Security baseline",
    ):
        assert required.lower() in readme.lower()

    assert "Phase 2 media sources" in readme
    assert "remain roadmap items and are not implemented" in readme
    assert "real-local acceptance tracked in the Phase 1 report" in readme


def test_windows_scripts_cover_runtime_readiness_and_every_deterministic_gate() -> None:
    development = (PROJECT_ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    verification = (PROJECT_ROOT / "scripts" / "verify.ps1").read_text(encoding="utf-8")

    for required in (
        "SUBTITLE_FORGE_DATA_ROOT",
        "/readiness",
        "jobs.sqlite3",
        "Stop-Process",
        "finally",
    ):
        assert required in development
    assert "Remove-Item -Recurse" not in development

    for required in (
        "Backend format",
        "Backend lint",
        "Backend types",
        "Backend tests",
        "Phase 1 API and artifact integration",
        "Frontend format",
        "Frontend lint",
        "Frontend types",
        "Frontend tests",
        "Frontend build",
        "Browser smoke test",
        "Secret signature scan",
        "OpenSpec strict validation",
        "exit $exitCode",
        "--no-incremental",
        "--cache-dir",
        "mypy-cache",
    ):
        assert required in verification
    for group in ("backend", "frontend", "security", "browser", "openspec"):
        assert f'-Group "{group}"' in verification
