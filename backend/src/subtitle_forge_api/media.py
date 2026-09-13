"""Safe subprocess boundaries for local media inspection."""

import json
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.storage import ManagedJobStorage


class MediaInspectionError(ValueError):
    """Safe media inspection failure suitable for user-facing guidance."""


class AudioExtractionError(ValueError):
    """Safe audio preparation failure suitable for user-facing guidance."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class MediaInspection:
    format_name: str
    duration_ms: int
    has_audio: bool
    audio_codec: str


@dataclass(frozen=True)
class PreparedAudio:
    path: Path
    converted: bool
    disposable: bool


ProcessRunner = Callable[[list[str], int], ProcessResult]


def run_process(arguments: list[str], timeout_seconds: int) -> ProcessResult:
    completed = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )
    return ProcessResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class MediaProbe:
    def __init__(
        self,
        *,
        executable: str = "ffprobe",
        timeout_seconds: int = 30,
        output_limit_bytes: int = 1_048_576,
        runner: ProcessRunner = run_process,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if output_limit_bytes < 1:
            raise ValueError("output_limit_bytes must be positive")
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._output_limit_bytes = output_limit_bytes
        self._runner = runner

    def inspect(
        self,
        media_path: Path,
        *,
        expected_type: SourceType,
    ) -> MediaInspection:
        if expected_type not in {SourceType.MP3, SourceType.MP4}:
            raise MediaInspectionError("Only MP3 and MP4 media can be inspected")
        if not media_path.is_file():
            raise MediaInspectionError("The media file is unavailable")

        arguments = [
            self._executable,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(media_path),
        ]
        try:
            result = self._runner(arguments, self._timeout_seconds)
        except FileNotFoundError as error:
            raise MediaInspectionError(
                "Media inspection is unavailable; install FFmpeg and ffprobe"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise MediaInspectionError("Media inspection timed out") from error
        except OSError as error:
            raise MediaInspectionError("Media inspection is unavailable") from error

        if result.returncode != 0:
            raise MediaInspectionError("The uploaded media is not readable")
        if _encoded_size(result.stdout) + _encoded_size(result.stderr) > (self._output_limit_bytes):
            raise MediaInspectionError("Media inspection output is too large")

        try:
            payload: Any = json.loads(result.stdout)
            return _parse_inspection(payload, expected_type)
        except MediaInspectionError:
            raise
        except (TypeError, ValueError, OverflowError, KeyError) as error:
            raise MediaInspectionError("Media returned invalid inspection data") from error


class AudioExtractor:
    def __init__(
        self,
        *,
        executable: str = "ffmpeg",
        timeout_seconds: int = 300,
        output_limit_bytes: int = 1_048_576,
        runner: ProcessRunner = run_process,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if output_limit_bytes < 1:
            raise ValueError("output_limit_bytes must be positive")
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._output_limit_bytes = output_limit_bytes
        self._runner = runner

    def prepare(
        self,
        *,
        storage: ManagedJobStorage,
        job_id: str,
        source_path: Path,
        source_type: SourceType,
        inspection: MediaInspection,
    ) -> PreparedAudio:
        expected_source = storage.resolve_member(
            job_id,
            f"source.{source_type.value}",
        )
        if source_path.resolve() != expected_source or not source_path.is_file():
            raise AudioExtractionError("The source media is unavailable")
        if not inspection.has_audio or not inspection.audio_codec:
            raise AudioExtractionError("Media does not contain a readable audio stream")

        if source_type is SourceType.MP3 and inspection.audio_codec.lower() == "mp3":
            return PreparedAudio(
                path=source_path,
                converted=False,
                disposable=False,
            )
        if source_type not in {SourceType.MP3, SourceType.MP4}:
            raise AudioExtractionError("The media source cannot be prepared")

        temporary_filename = f".audio.{uuid4().hex}.wav"
        temporary = storage.resolve_member(job_id, temporary_filename)
        arguments = [
            self._executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(temporary),
        ]
        try:
            result = self._runner(arguments, self._timeout_seconds)
            if result.returncode != 0:
                raise AudioExtractionError("FFmpeg could not prepare the media audio")
            if _encoded_size(result.stdout) + _encoded_size(result.stderr) > (
                self._output_limit_bytes
            ):
                raise AudioExtractionError("Audio preparation output is too large")
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise AudioExtractionError("FFmpeg did not produce prepared audio")

            destination = storage.publish_temporary(
                job_id,
                temporary_filename,
                "audio.wav",
            )
        except AudioExtractionError:
            raise
        except FileNotFoundError as error:
            raise AudioExtractionError(
                "Audio preparation is unavailable; install FFmpeg"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AudioExtractionError("Audio preparation timed out") from error
        except OSError as error:
            raise AudioExtractionError("Audio preparation is unavailable") from error
        finally:
            temporary.unlink(missing_ok=True)

        return PreparedAudio(path=destination, converted=True, disposable=True)


def _encoded_size(value: str) -> int:
    return len(value.encode("utf-8", errors="replace"))


def _parse_inspection(payload: Any, expected_type: SourceType) -> MediaInspection:
    if not isinstance(payload, dict):
        raise MediaInspectionError("Media returned invalid inspection data")

    format_payload = payload.get("format")
    streams_payload = payload.get("streams")
    if not isinstance(format_payload, dict) or not isinstance(streams_payload, list):
        raise MediaInspectionError("Media returned invalid inspection data")

    format_name = format_payload.get("format_name")
    duration_value = format_payload.get("duration")
    if not isinstance(format_name, str) or not isinstance(duration_value, (str, int, float)):
        raise MediaInspectionError("Media returned invalid inspection data")

    format_components = set(format_name.lower().split(","))
    required_format = expected_type.value
    if required_format not in format_components:
        raise MediaInspectionError(
            f"Uploaded content does not match declared {expected_type.value.upper()} type"
        )

    duration_seconds = float(duration_value)
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise MediaInspectionError("Media duration must be positive and finite")

    audio_codec = ""
    for stream in streams_payload:
        if isinstance(stream, dict) and stream.get("codec_type") == "audio":
            codec_name = stream.get("codec_name")
            if isinstance(codec_name, str) and codec_name:
                audio_codec = codec_name
                break
    if not audio_codec:
        raise MediaInspectionError("Media does not contain a readable audio stream")

    return MediaInspection(
        format_name=format_name,
        duration_ms=round(duration_seconds * 1_000),
        has_audio=True,
        audio_codec=audio_codec,
    )
