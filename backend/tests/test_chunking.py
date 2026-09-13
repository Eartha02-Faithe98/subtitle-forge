import pytest

from subtitle_forge_api.chunking import (
    AudioChunk,
    ChunkTranscription,
    merge_chunk_transcriptions,
    plan_audio_chunks,
)
from subtitle_forge_api.domain import TranscriptSegment, WordSegment


def segment(
    segment_id: str,
    start_ms: int,
    end_ms: int,
    text: str,
    *,
    words: tuple[WordSegment, ...] = (),
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=segment_id,
        start_ms=start_ms,
        end_ms=end_ms,
        source_text=text,
        words=words,
    )


def test_plans_bounded_chunks_with_exact_overlap_and_final_tail() -> None:
    chunks = plan_audio_chunks(
        duration_ms=2_050_000,
        max_chunk_ms=900_000,
        overlap_ms=5_000,
    )

    assert chunks == (
        AudioChunk(index=0, start_ms=0, end_ms=900_000),
        AudioChunk(index=1, start_ms=895_000, end_ms=1_795_000),
        AudioChunk(index=2, start_ms=1_790_000, end_ms=2_050_000),
    )
    assert all(chunk.duration_ms <= 900_000 for chunk in chunks)


def test_short_audio_uses_one_chunk() -> None:
    assert plan_audio_chunks(
        duration_ms=1_000,
        max_chunk_ms=900_000,
        overlap_ms=5_000,
    ) == (AudioChunk(index=0, start_ms=0, end_ms=1_000),)


def test_zero_overlap_chunks_can_be_merged_without_a_gap() -> None:
    chunks = plan_audio_chunks(duration_ms=2_000, max_chunk_ms=1_000, overlap_ms=0)

    merged = merge_chunk_transcriptions(
        (
            ChunkTranscription(
                chunk=chunks[0],
                segments=(segment("a", 0, 500, "First"),),
            ),
            ChunkTranscription(
                chunk=chunks[1],
                segments=(segment("b", 0, 500, "Second"),),
            ),
        )
    )

    assert [(item.start_ms, item.source_text) for item in merged] == [
        (0, "First"),
        (1_000, "Second"),
    ]


@pytest.mark.parametrize(
    ("duration_ms", "max_chunk_ms", "overlap_ms"),
    [(0, 100, 5), (-1, 100, 5), (100, 0, 0), (100, 10, -1), (100, 10, 10)],
)
def test_invalid_chunk_bounds_are_rejected(
    duration_ms: int,
    max_chunk_ms: int,
    overlap_ms: int,
) -> None:
    with pytest.raises(ValueError):
        plan_audio_chunks(duration_ms, max_chunk_ms, overlap_ms)


def test_merge_offsets_words_and_removes_overlap_duplicate_text() -> None:
    first = AudioChunk(index=0, start_ms=0, end_ms=10_000)
    second = AudioChunk(index=1, start_ms=9_000, end_ms=18_000)
    merged = merge_chunk_transcriptions(
        (
            ChunkTranscription(
                chunk=first,
                segments=(
                    segment("local-a", 8_000, 9_000, "Hello"),
                    segment("local-b", 9_200, 9_800, "Shared phrase."),
                ),
            ),
            ChunkTranscription(
                chunk=second,
                segments=(
                    segment("local-c", 200, 800, " Shared   phrase. "),
                    segment(
                        "local-d",
                        1_000,
                        2_000,
                        "Next words",
                        words=(
                            WordSegment(start_ms=1_000, end_ms=1_400, text="Next"),
                            WordSegment(start_ms=1_500, end_ms=2_000, text="words"),
                        ),
                    ),
                ),
            ),
        )
    )

    assert [item.segment_id for item in merged] == [
        "segment-000001",
        "segment-000002",
        "segment-000003",
    ]
    assert [item.source_text for item in merged] == [
        "Hello",
        "Shared phrase.",
        "Next words",
    ]
    assert [(item.start_ms, item.end_ms) for item in merged] == [
        (8_000, 9_000),
        (9_200, 9_800),
        (10_000, 11_000),
    ]
    assert [(word.start_ms, word.end_ms) for word in merged[-1].words] == [
        (10_000, 10_400),
        (10_500, 11_000),
    ]


def test_merge_is_chronological_even_if_provider_segments_are_reversed() -> None:
    chunk = AudioChunk(index=0, start_ms=0, end_ms=5_000)

    merged = merge_chunk_transcriptions(
        (
            ChunkTranscription(
                chunk=chunk,
                segments=(
                    segment("later", 2_000, 3_000, "Later"),
                    segment("earlier", 100, 500, "Earlier"),
                ),
            ),
        )
    )

    assert [item.source_text for item in merged] == ["Earlier", "Later"]


def test_merge_rejects_segment_outside_its_chunk() -> None:
    chunk = AudioChunk(index=0, start_ms=1_000, end_ms=2_000)

    with pytest.raises(ValueError, match="chunk bounds"):
        merge_chunk_transcriptions(
            (
                ChunkTranscription(
                    chunk=chunk,
                    segments=(segment("bad", 0, 1_500, "Too long"),),
                ),
            )
        )
