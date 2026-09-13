from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from subtitle_forge_api.chunking import AudioChunk
from subtitle_forge_api.domain import Transcript, TranscriptSegment
from subtitle_forge_api.media import ProcessResult
from subtitle_forge_api.whisper import NoSpeechDetectedError
from subtitle_forge_api.whisper_orchestration import (
    ChunkedWhisperTranscriber,
    FfmpegChunkMaterializer,
)


def transcript(*segments: TranscriptSegment) -> Transcript:
    return Transcript(segments=segments)


def item(identifier: str, start_ms: int, end_ms: int, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=identifier,
        start_ms=start_ms,
        end_ms=end_ms,
        source_text=text,
    )


class FakeSpeechProvider:
    def __init__(self, responses: dict[str, Transcript | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def transcribe(self, audio_path: Path, progress=None) -> Transcript:  # type: ignore[no-untyped-def]
        self.calls.append(audio_path.name)
        if progress is not None:
            progress(0.5)
            progress(1.0)
        response = self.responses[audio_path.name]
        if isinstance(response, Exception):
            raise response
        return response


class FakeMaterializer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[AudioChunk] = []

    @contextmanager
    def materialize(self, source_path: Path, chunk: AudioChunk) -> Iterator[Path]:
        del source_path
        self.calls.append(chunk)
        path = self.root / f"chunk-{chunk.index}.wav"
        path.write_bytes(b"RIFFchunk")
        try:
            yield path
        finally:
            path.unlink(missing_ok=True)


class ChunkRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, arguments: list[str], timeout_seconds: int) -> ProcessResult:
        self.calls.append((arguments, timeout_seconds))
        Path(arguments[-1]).write_bytes(b"RIFFbounded")
        return ProcessResult(0, "", "")


def test_default_materializer_uses_bounded_ffmpeg_arguments_and_cleans_up(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFaudio")
    runner = ChunkRunner()
    materializer = FfmpegChunkMaterializer(
        executable="custom-ffmpeg",
        timeout_seconds=44,
        runner=runner,
    )

    with materializer.materialize(
        audio,
        AudioChunk(index=2, start_ms=1_500, end_ms=3_750),
    ) as chunk_path:
        assert chunk_path.read_bytes() == b"RIFFbounded"
        assert chunk_path.parent == audio.parent

    arguments, timeout = runner.calls[0]
    assert timeout == 44
    assert arguments[0] == "custom-ffmpeg"
    assert arguments[arguments.index("-ss") + 1] == "1.500"
    assert arguments[arguments.index("-t") + 1] == "2.250"
    assert arguments[arguments.index("-i") + 1] == str(audio)
    assert Path(arguments[-1]).exists() is False


def test_one_chunk_avoids_materialization_and_stabilizes_reversed_results(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFaudio")
    reversed_result = Transcript.model_construct(
        language="en",
        segments=(item("b", 800, 900, "Later"), item("a", 100, 200, "Earlier")),
    )
    provider = FakeSpeechProvider({"audio.wav": reversed_result})
    materializer = FakeMaterializer(tmp_path)

    result = ChunkedWhisperTranscriber(
        provider=provider,
        materializer=materializer,
        max_chunk_ms=1_000,
        overlap_ms=100,
    ).transcribe(audio, duration_ms=900)

    assert materializer.calls == []
    assert [segment.source_text for segment in result.segments] == ["Earlier", "Later"]
    assert [segment.segment_id for segment in result.segments] == [
        "segment-000001",
        "segment-000002",
    ]


def test_multiple_chunks_keep_long_media_offsets_and_global_progress(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFaudio")
    provider = FakeSpeechProvider(
        {
            "chunk-0.wav": transcript(item("a", 100, 200, "First")),
            "chunk-1.wav": transcript(item("b", 100, 200, "Second")),
            "chunk-2.wav": transcript(item("c", 100, 200, "Third")),
        }
    )
    materializer = FakeMaterializer(tmp_path)
    progress: list[float] = []

    result = ChunkedWhisperTranscriber(
        provider=provider,
        materializer=materializer,
        max_chunk_ms=1_000,
        overlap_ms=100,
    ).transcribe(audio, duration_ms=2_500, progress=progress.append)

    assert [(segment.start_ms, segment.source_text) for segment in result.segments] == [
        (100, "First"),
        (1_000, "Second"),
        (1_900, "Third"),
    ]
    assert [chunk.start_ms for chunk in materializer.calls] == [0, 900, 1_800]
    assert progress[0] == 0.0
    assert progress[-1] == 1.0
    assert progress == sorted(progress)
    assert not list(tmp_path.glob("chunk-*.wav"))


def test_silent_chunks_are_skipped_but_all_silence_fails_safely(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFaudio")
    silent = NoSpeechDetectedError("no speech")
    materializer = FakeMaterializer(tmp_path)
    partly_silent = FakeSpeechProvider(
        {
            "chunk-0.wav": silent,
            "chunk-1.wav": transcript(item("b", 100, 200, "Spoken")),
        }
    )

    result = ChunkedWhisperTranscriber(
        provider=partly_silent,
        materializer=materializer,
        max_chunk_ms=1_000,
        overlap_ms=100,
    ).transcribe(audio, duration_ms=1_500)

    assert result.segments[0].start_ms == 1_000

    all_silent = FakeSpeechProvider({"chunk-0.wav": silent, "chunk-1.wav": silent})
    with pytest.raises(NoSpeechDetectedError, match="recognizable English speech"):
        ChunkedWhisperTranscriber(
            provider=all_silent,
            materializer=FakeMaterializer(tmp_path),
            max_chunk_ms=1_000,
            overlap_ms=100,
        ).transcribe(audio, duration_ms=1_500)
