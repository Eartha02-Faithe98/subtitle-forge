import pytest

from subtitle_forge_api.domain import (
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.rendering import (
    ArtifactAlignmentError,
    render_english_transcript,
    render_traditional_chinese_transcript,
)


def source_transcript() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(
                segment_id="segment-000001",
                start_ms=125,
                end_ms=1_500,
                source_text="Hello, world!",
            ),
            TranscriptSegment(
                segment_id="segment-000002",
                start_ms=3_661_999,
                end_ms=3_663_000,
                source_text="Café — déjà vu?",
            ),
        )
    )


def translated_transcript() -> TranslatedTranscript:
    return TranslatedTranscript(
        segments=(
            TranslatedSegment(
                segment_id="segment-000001",
                start_ms=125,
                end_ms=1_500,
                translated_text="哈囉，世界！",
            ),
            TranslatedSegment(
                segment_id="segment-000002",
                start_ms=3_661_999,
                end_ms=3_663_000,
                translated_text="似曾相識？",
            ),
        )
    )


def test_english_transcript_has_stable_timestamps_utf8_and_lf() -> None:
    rendered = render_english_transcript(source_transcript())

    assert rendered == ("[00:00:00] Hello, world!\n[01:01:01] Café — déjà vu?\n")
    assert rendered.encode("utf-8") == (
        b"[00:00:00] Hello, world!\n[01:01:01] Caf\xc3\xa9 \xe2\x80\x94 d\xc3\xa9j\xc3\xa0 vu?\n"
    )
    assert "\r" not in rendered


def test_traditional_chinese_uses_matching_source_order_and_timestamps() -> None:
    rendered = render_traditional_chinese_transcript(
        source_transcript(),
        translated_transcript(),
    )

    assert rendered == "[00:00:00] 哈囉，世界！\n[01:01:01] 似曾相識？\n"
    assert rendered.encode("utf-8").decode("utf-8") == rendered


@pytest.mark.parametrize(
    "translated",
    [
        TranslatedTranscript(
            segments=(
                TranslatedSegment(
                    segment_id="segment-000002",
                    start_ms=3_661_999,
                    end_ms=3_663_000,
                    translated_text="順序錯誤",
                ),
            )
        ),
        TranslatedTranscript(
            segments=(
                TranslatedSegment(
                    segment_id="segment-000001",
                    start_ms=999,
                    end_ms=1_500,
                    translated_text="時間錯誤",
                ),
                TranslatedSegment(
                    segment_id="segment-000002",
                    start_ms=3_661_999,
                    end_ms=3_663_000,
                    translated_text="第二段",
                ),
            )
        ),
    ],
)
def test_traditional_chinese_rejects_incomplete_reordered_or_retimed_segments(
    translated: TranslatedTranscript,
) -> None:
    with pytest.raises(ArtifactAlignmentError, match="align"):
        render_traditional_chinese_transcript(source_transcript(), translated)
