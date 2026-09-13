from subtitle_forge_api.domain import (
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.srt import (
    render_bilingual_srt,
    render_english_srt,
    render_traditional_chinese_srt,
)
from subtitle_forge_api.subtitles import SubtitleCue


def source() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(
                segment_id="s1",
                start_ms=125,
                end_ms=1_500,
                source_text="Hello, world!",
            ),
            TranscriptSegment(
                segment_id="s2",
                start_ms=3_661_999,
                end_ms=3_663_005,
                source_text="Second line.",
            ),
        )
    )


def translated() -> TranslatedTranscript:
    return TranslatedTranscript(
        segments=(
            TranslatedSegment(
                segment_id="s1",
                start_ms=125,
                end_ms=1_500,
                translated_text="哈囉，世界！",
            ),
            TranslatedSegment(
                segment_id="s2",
                start_ms=3_661_999,
                end_ms=3_663_005,
                translated_text="第二行。",
            ),
        )
    )


def test_english_srt_has_sequential_indices_millisecond_codes_and_lf() -> None:
    cues = (
        SubtitleCue(125, 1_500, "Hello, world!", ("s1",)),
        SubtitleCue(3_661_999, 3_663_005, "Second line.", ("s2",)),
    )

    rendered = render_english_srt(cues)

    assert rendered == (
        "1\n00:00:00,125 --> 00:00:01,500\nHello, world!\n\n"
        "2\n01:01:01,999 --> 01:01:03,005\nSecond line.\n\n"
    )
    assert "\r" not in rendered


def test_traditional_chinese_and_bilingual_srt_are_deterministic() -> None:
    chinese_first = render_traditional_chinese_srt(source(), translated())
    chinese_second = render_traditional_chinese_srt(source(), translated())
    bilingual_first = render_bilingual_srt(source(), translated())
    bilingual_second = render_bilingual_srt(source(), translated())

    assert chinese_first == chinese_second
    assert chinese_first == (
        "1\n00:00:00,125 --> 00:00:01,500\n哈囉，世界！\n\n"
        "2\n01:01:01,999 --> 01:01:03,005\n第二行。\n\n"
    )
    assert bilingual_first == bilingual_second
    assert bilingual_first == (
        "1\n00:00:00,125 --> 00:00:01,500\nHello, world!\n哈囉，世界！\n\n"
        "2\n01:01:01,999 --> 01:01:03,005\nSecond line.\n第二行。\n\n"
    )
    assert bilingual_first.encode("utf-8").decode("utf-8") == bilingual_first


def test_bilingual_cue_languages_share_exactly_one_interval() -> None:
    blocks = render_bilingual_srt(source(), translated()).strip().split("\n\n")

    for block in blocks:
        lines = block.splitlines()
        assert len(lines) == 4
        assert lines[1].count(" --> ") == 1
