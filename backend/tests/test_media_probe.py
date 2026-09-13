import json
import subprocess
from pathlib import Path

import pytest

from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.media import (
    MediaInspectionError,
    MediaProbe,
    ProcessResult,
)


class FakeRunner:
    def __init__(
        self,
        result: ProcessResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, arguments: list[str], timeout_seconds: int) -> ProcessResult:
        self.calls.append((arguments, timeout_seconds))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def probe_result(
    *,
    format_name: str,
    duration: str = "12.345",
    codec_type: str = "audio",
    codec_name: str = "aac",
) -> ProcessResult:
    return ProcessResult(
        returncode=0,
        stdout=json.dumps(
            {
                "format": {"format_name": format_name, "duration": duration},
                "streams": [{"codec_type": codec_type, "codec_name": codec_name}],
            }
        ),
        stderr="",
    )


@pytest.mark.parametrize(
    ("source_type", "format_name", "codec_name"),
    [
        (SourceType.MP3, "mp3", "mp3"),
        (SourceType.MP4, "mov,mp4,m4a,3gp,3g2,mj2", "aac"),
    ],
)
def test_probe_parses_supported_media_without_shell_interpolation(
    tmp_path: Path,
    source_type: SourceType,
    format_name: str,
    codec_name: str,
) -> None:
    media_path = tmp_path / f"source;$(unsafe).{source_type.value}"
    media_path.write_bytes(b"fixture")
    runner = FakeRunner(probe_result(format_name=format_name, codec_name=codec_name))

    inspection = MediaProbe(
        executable="custom-ffprobe",
        timeout_seconds=17,
        runner=runner,
    ).inspect(media_path, expected_type=source_type)

    assert inspection.duration_ms == 12_345
    assert inspection.format_name == format_name
    assert inspection.audio_codec == codec_name
    assert inspection.has_audio is True
    assert runner.calls == [
        (
            [
                "custom-ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(media_path),
            ],
            17,
        )
    ]


@pytest.mark.parametrize(
    ("runner", "message"),
    [
        (FakeRunner(error=FileNotFoundError("private executable path")), "unavailable"),
        (
            FakeRunner(error=subprocess.TimeoutExpired("secret command", 3)),
            "timed out",
        ),
        (
            FakeRunner(ProcessResult(1, "", "C:\\secret\\media.mp3: corrupt")),
            "not readable",
        ),
        (FakeRunner(ProcessResult(0, "not json", "")), "invalid inspection"),
    ],
)
def test_probe_maps_dependency_timeout_corrupt_and_json_errors_safely(
    tmp_path: Path,
    runner: FakeRunner,
    message: str,
) -> None:
    media_path = tmp_path / "private-source.mp3"
    media_path.write_bytes(b"fixture")

    with pytest.raises(MediaInspectionError, match=message) as captured:
        MediaProbe(runner=runner).inspect(media_path, expected_type=SourceType.MP3)

    safe_message = str(captured.value)
    assert "secret" not in safe_message
    assert str(media_path) not in safe_message
    assert "corrupt" not in safe_message


def test_probe_rejects_oversized_output_before_parsing(tmp_path: Path) -> None:
    media_path = tmp_path / "source.mp3"
    media_path.write_bytes(b"fixture")
    runner = FakeRunner(ProcessResult(0, "{" + "x" * 100, ""))

    with pytest.raises(MediaInspectionError, match="too large"):
        MediaProbe(runner=runner, output_limit_bytes=64).inspect(
            media_path,
            expected_type=SourceType.MP3,
        )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (probe_result(format_name="wav"), "declared MP3"),
        (probe_result(format_name="mp3", duration="nan"), "duration"),
        (probe_result(format_name="mp3", duration="0"), "duration"),
        (
            probe_result(format_name="mp3", codec_type="video", codec_name="h264"),
            "audio stream",
        ),
    ],
)
def test_probe_rejects_wrong_type_invalid_duration_and_missing_audio(
    tmp_path: Path,
    result: ProcessResult,
    message: str,
) -> None:
    media_path = tmp_path / "source.mp3"
    media_path.write_bytes(b"fixture")

    with pytest.raises(MediaInspectionError, match=message):
        MediaProbe(runner=FakeRunner(result)).inspect(
            media_path,
            expected_type=SourceType.MP3,
        )


def test_probe_rejects_missing_input_without_invoking_ffprobe(tmp_path: Path) -> None:
    runner = FakeRunner(probe_result(format_name="mp3"))

    with pytest.raises(MediaInspectionError, match="unavailable"):
        MediaProbe(runner=runner).inspect(
            tmp_path / "missing.mp3",
            expected_type=SourceType.MP3,
        )

    assert runner.calls == []
