"""Bounded audio chunk planning and original-timeline transcript merging."""

import re
from dataclasses import dataclass

from subtitle_forge_api.domain import TranscriptSegment, WordSegment

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class AudioChunk:
    index: int
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("chunk index must be non-negative")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("chunk bounds must form a positive interval")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True)
class ChunkTranscription:
    chunk: AudioChunk
    segments: tuple[TranscriptSegment, ...]


@dataclass(frozen=True)
class _GlobalSegment:
    start_ms: int
    end_ms: int
    source_text: str
    words: tuple[WordSegment, ...]


def plan_audio_chunks(
    duration_ms: int,
    max_chunk_ms: int,
    overlap_ms: int,
) -> tuple[AudioChunk, ...]:
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if max_chunk_ms <= 0:
        raise ValueError("max_chunk_ms must be positive")
    if overlap_ms < 0 or overlap_ms >= max_chunk_ms:
        raise ValueError("overlap_ms must be non-negative and smaller than a chunk")

    chunks: list[AudioChunk] = []
    start_ms = 0
    while start_ms < duration_ms:
        end_ms = min(start_ms + max_chunk_ms, duration_ms)
        chunks.append(AudioChunk(index=len(chunks), start_ms=start_ms, end_ms=end_ms))
        if end_ms == duration_ms:
            break
        start_ms = end_ms - overlap_ms
    return tuple(chunks)


def merge_chunk_transcriptions(
    transcriptions: tuple[ChunkTranscription, ...],
) -> tuple[TranscriptSegment, ...]:
    if not transcriptions:
        return ()
    _validate_chunk_order(transcriptions)

    accepted: list[_GlobalSegment] = []
    previous_chunk_end: int | None = None
    for transcription in transcriptions:
        chunk = transcription.chunk
        ownership_start = previous_chunk_end
        for local in transcription.segments:
            if local.end_ms > chunk.duration_ms:
                raise ValueError("transcript segment must stay inside chunk bounds")
            global_segment = _offset_segment(local, chunk.start_ms)
            if ownership_start is not None and global_segment.end_ms <= ownership_start:
                continue
            if _is_overlap_duplicate(global_segment, accepted, chunk.start_ms):
                continue
            accepted.append(global_segment)
        previous_chunk_end = chunk.end_ms

    accepted.sort(key=lambda item: (item.start_ms, item.end_ms, item.source_text))
    return tuple(
        TranscriptSegment(
            segment_id=f"segment-{index:06d}",
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            source_text=item.source_text,
            words=item.words,
        )
        for index, item in enumerate(accepted, start=1)
    )


def _validate_chunk_order(transcriptions: tuple[ChunkTranscription, ...]) -> None:
    for expected_index, transcription in enumerate(transcriptions):
        if transcription.chunk.index != expected_index:
            raise ValueError("chunk transcriptions must use consecutive indexes")
        if expected_index > 0:
            previous = transcriptions[expected_index - 1].chunk
            if transcription.chunk.start_ms > previous.end_ms:
                raise ValueError("adjacent chunks must overlap or meet without a gap")
            if transcription.chunk.end_ms <= previous.end_ms:
                raise ValueError("chunk end times must advance")


def _offset_segment(segment: TranscriptSegment, offset_ms: int) -> _GlobalSegment:
    words = tuple(
        WordSegment(
            start_ms=word.start_ms + offset_ms,
            end_ms=word.end_ms + offset_ms,
            text=word.text,
        )
        for word in segment.words
    )
    return _GlobalSegment(
        start_ms=segment.start_ms + offset_ms,
        end_ms=segment.end_ms + offset_ms,
        source_text=segment.source_text,
        words=words,
    )


def _is_overlap_duplicate(
    candidate: _GlobalSegment,
    accepted: list[_GlobalSegment],
    chunk_start_ms: int,
) -> bool:
    normalized = _normalize_text(candidate.source_text)
    return any(
        _normalize_text(existing.source_text) == normalized
        and existing.end_ms > chunk_start_ms
        and candidate.start_ms < existing.end_ms
        and existing.start_ms < candidate.end_ms
        for existing in accepted
    )


def _normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip().casefold()
