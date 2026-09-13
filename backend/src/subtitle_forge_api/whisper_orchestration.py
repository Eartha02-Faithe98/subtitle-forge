"""Bounded Local Whisper orchestration over temporary audio chunks."""

import subprocess
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from subtitle_forge_api.chunking import (
    AudioChunk,
    ChunkTranscription,
    merge_chunk_transcriptions,
    plan_audio_chunks,
)
from subtitle_forge_api.domain import Transcript
from subtitle_forge_api.media import ProcessRunner, run_process
from subtitle_forge_api.providers import ProgressCallback, SpeechToTextProvider
from subtitle_forge_api.whisper import NoSpeechDetectedError, WhisperUnavailableError


class ChunkAudioMaterializer(Protocol):
    def materialize(
        self,
        source_path: Path,
        chunk: AudioChunk,
    ) -> AbstractContextManager[Path]: ...


class FfmpegChunkMaterializer:
    def __init__(
        self,
        *,
        executable: str = "ffmpeg",
        timeout_seconds: int = 300,
        output_limit_bytes: int = 1_048_576,
        runner: ProcessRunner = run_process,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._output_limit_bytes = output_limit_bytes
        self._runner = runner

    @contextmanager
    def materialize(self, source_path: Path, chunk: AudioChunk) -> Iterator[Path]:
        if not source_path.is_file():
            raise WhisperUnavailableError("Prepared audio is unavailable")
        output = source_path.parent / (f".whisper-chunk-{chunk.index:06d}-{uuid4().hex}.wav")
        arguments = [
            self._executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{chunk.start_ms / 1_000:.3f}",
            "-t",
            f"{chunk.duration_ms / 1_000:.3f}",
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
            str(output),
        ]
        try:
            result = self._runner(arguments, self._timeout_seconds)
            if result.returncode != 0:
                raise WhisperUnavailableError("Could not prepare a bounded audio chunk")
            output_size = len(result.stdout.encode(errors="replace")) + len(
                result.stderr.encode(errors="replace")
            )
            if output_size > self._output_limit_bytes:
                raise WhisperUnavailableError("Audio chunk tool output is too large")
            if not output.is_file() or output.stat().st_size == 0:
                raise WhisperUnavailableError("Audio chunk preparation produced no audio")
            yield output
        except WhisperUnavailableError:
            raise
        except FileNotFoundError as error:
            raise WhisperUnavailableError(
                "Audio chunk preparation is unavailable; install FFmpeg"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise WhisperUnavailableError("Audio chunk preparation timed out") from error
        except OSError as error:
            raise WhisperUnavailableError("Audio chunk preparation is unavailable") from error
        finally:
            output.unlink(missing_ok=True)


class ChunkedWhisperTranscriber:
    def __init__(
        self,
        *,
        provider: SpeechToTextProvider,
        max_chunk_ms: int,
        overlap_ms: int,
        materializer: ChunkAudioMaterializer | None = None,
    ) -> None:
        self._provider = provider
        self._max_chunk_ms = max_chunk_ms
        self._overlap_ms = overlap_ms
        self._materializer = materializer or FfmpegChunkMaterializer()

    def transcribe(
        self,
        audio_path: Path,
        *,
        duration_ms: int,
        progress: ProgressCallback | None = None,
    ) -> Transcript:
        chunks = plan_audio_chunks(
            duration_ms,
            self._max_chunk_ms,
            self._overlap_ms,
        )
        report = progress or _ignore_progress
        report(0.0)
        transcriptions: list[ChunkTranscription] = []
        saw_speech = False

        for index, chunk in enumerate(chunks):
            local_progress = _map_progress(report, index, len(chunks))
            try:
                if len(chunks) == 1:
                    transcript = self._provider.transcribe(audio_path, local_progress)
                else:
                    with self._materializer.materialize(audio_path, chunk) as chunk_path:
                        transcript = self._provider.transcribe(
                            chunk_path,
                            local_progress,
                        )
            except NoSpeechDetectedError:
                transcriptions.append(ChunkTranscription(chunk=chunk, segments=()))
                report((index + 1) / len(chunks))
                continue
            saw_speech = True
            transcriptions.append(ChunkTranscription(chunk=chunk, segments=transcript.segments))
            report((index + 1) / len(chunks))

        if not saw_speech:
            raise NoSpeechDetectedError("Local Whisper found no recognizable English speech")
        merged = merge_chunk_transcriptions(tuple(transcriptions))
        if not merged:
            raise NoSpeechDetectedError("Local Whisper found no recognizable English speech")
        report(1.0)
        return Transcript(segments=merged)


def _map_progress(
    report: ProgressCallback,
    chunk_index: int,
    chunk_count: int,
) -> ProgressCallback:
    def mapped(value: float) -> None:
        bounded = min(1.0, max(0.0, value))
        report((chunk_index + bounded) / chunk_count)

    return mapped


def _ignore_progress(value: float) -> None:
    del value
