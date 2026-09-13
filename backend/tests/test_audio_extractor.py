import subprocess
from pathlib import Path

import pytest

from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.media import (
    AudioExtractionError,
    AudioExtractor,
    MediaInspection,
    ProcessResult,
)
from subtitle_forge_api.storage import ManagedJobStorage


class ExtractRunner:
    def __init__(
        self,
        *,
        result: ProcessResult | None = None,
        error: Exception | None = None,
        write_output: bool = True,
    ) -> None:
        self.result = result or ProcessResult(0, "", "")
        self.error = error
        self.write_output = write_output
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, arguments: list[str], timeout_seconds: int) -> ProcessResult:
        self.calls.append((arguments, timeout_seconds))
        if self.error is not None:
            raise self.error
        if self.write_output:
            Path(arguments[-1]).write_bytes(b"RIFFprepared-wave")
        return self.result


def inspection(codec: str = "mp3", *, has_audio: bool = True) -> MediaInspection:
    return MediaInspection(
        format_name="mp3",
        duration_ms=5_000,
        has_audio=has_audio,
        audio_codec=codec,
    )


def test_supported_mp3_is_passed_through_without_ffmpeg(tmp_path: Path) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    source = storage.write_atomic(job.job_id, "source.mp3", b"ID3fixture")
    runner = ExtractRunner()

    prepared = AudioExtractor(runner=runner).prepare(
        storage=storage,
        job_id=job.job_id,
        source_path=source,
        source_type=SourceType.MP3,
        inspection=inspection(),
    )

    assert prepared.path == source
    assert prepared.converted is False
    assert prepared.disposable is False
    assert runner.calls == []


@pytest.mark.parametrize(
    ("source_type", "codec"),
    [(SourceType.MP3, "aac"), (SourceType.MP4, "aac")],
)
def test_ffmpeg_normalizes_non_passthrough_audio_deterministically(
    tmp_path: Path,
    source_type: SourceType,
    codec: str,
) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    source = storage.write_atomic(
        job.job_id,
        f"source.{source_type.value}",
        b"fixture",
    )
    runner = ExtractRunner()

    prepared = AudioExtractor(
        executable="custom-ffmpeg",
        timeout_seconds=41,
        runner=runner,
    ).prepare(
        storage=storage,
        job_id=job.job_id,
        source_path=source,
        source_type=source_type,
        inspection=inspection(codec),
    )

    assert prepared.path == storage.resolve_member(job.job_id, "audio.wav")
    assert prepared.path.read_bytes() == b"RIFFprepared-wave"
    assert prepared.converted is True
    assert prepared.disposable is True
    arguments, timeout = runner.calls[0]
    assert timeout == 41
    assert arguments[:-1] == [
        "custom-ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
    ]
    assert Path(arguments[-1]).parent == source.parent
    assert list(source.parent.glob(".*.wav")) == []


def test_missing_audio_fails_without_running_ffmpeg(tmp_path: Path) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    source = storage.write_atomic(job.job_id, "source.mp4", b"fixture")
    runner = ExtractRunner()

    with pytest.raises(AudioExtractionError, match="audio stream"):
        AudioExtractor(runner=runner).prepare(
            storage=storage,
            job_id=job.job_id,
            source_path=source,
            source_type=SourceType.MP4,
            inspection=inspection("", has_audio=False),
        )

    assert runner.calls == []


@pytest.mark.parametrize(
    ("runner", "message"),
    [
        (ExtractRunner(error=FileNotFoundError("C:\\secret\\ffmpeg")), "unavailable"),
        (
            ExtractRunner(error=subprocess.TimeoutExpired("secret command", 4)),
            "timed out",
        ),
        (
            ExtractRunner(result=ProcessResult(1, "", "C:\\secret\\source.mp4 failed")),
            "could not prepare",
        ),
        (ExtractRunner(write_output=False), "did not produce"),
    ],
)
def test_extraction_failure_is_safe_and_removes_partial_output(
    tmp_path: Path,
    runner: ExtractRunner,
    message: str,
) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    source = storage.write_atomic(job.job_id, "source.mp4", b"fixture")

    with pytest.raises(AudioExtractionError, match=message) as captured:
        AudioExtractor(runner=runner).prepare(
            storage=storage,
            job_id=job.job_id,
            source_path=source,
            source_type=SourceType.MP4,
            inspection=inspection("aac"),
        )

    assert "secret" not in str(captured.value)
    assert str(source) not in str(captured.value)
    assert storage.resolve_member(job.job_id, "audio.wav").exists() is False
    assert list(source.parent.glob(".*.wav")) == []
