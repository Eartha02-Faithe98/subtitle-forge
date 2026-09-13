from subtitle_forge_api.domain import Transcript, TranscriptSegment, WordSegment
from subtitle_forge_api.subtitles import build_subtitle_cues, wrap_subtitle_text


def segment(
    identifier: str,
    start_ms: int,
    end_ms: int,
    text: str,
    *,
    words: tuple[WordSegment, ...] = (),
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=identifier,
        start_ms=start_ms,
        end_ms=end_ms,
        source_text=text,
        words=words,
    )


def test_merges_adjacent_short_fragments_but_respects_sentence_boundaries() -> None:
    transcript = Transcript(
        segments=(
            segment("s1", 0, 500, "Hello"),
            segment("s2", 600, 1_500, "world."),
            segment("s3", 1_600, 2_000, "Next"),
        )
    )

    cues = build_subtitle_cues(transcript)

    assert [(cue.start_ms, cue.end_ms, cue.text) for cue in cues] == [
        (0, 1_500, "Hello world."),
        (1_600, 2_000, "Next"),
    ]
    assert cues[0].segment_ids == ("s1", "s2")


def test_long_segment_splits_only_at_word_timing_boundaries() -> None:
    word_values = ("one", "two", "three", "four", "five", "six", "seven")
    words = tuple(
        WordSegment(
            start_ms=index * 500,
            end_ms=(index + 1) * 500,
            text=value,
        )
        for index, value in enumerate(word_values)
    )
    transcript = Transcript(
        segments=(segment("s1", 0, 3_500, "one two three four five six seven", words=words),)
    )

    cues = build_subtitle_cues(transcript, max_chars_per_cue=14)

    assert [(cue.start_ms, cue.end_ms, cue.text) for cue in cues] == [
        (0, 1_500, "one two three"),
        (1_500, 3_000, "four five six"),
        (3_000, 3_500, "seven"),
    ]
    assert all(cue.segment_ids == ("s1",) for cue in cues)


def test_long_segment_without_words_keeps_original_interval_as_fallback() -> None:
    source = segment(
        "s1",
        1_000,
        5_000,
        "This provider segment has no defensible word timing split.",
    )

    cues = build_subtitle_cues(
        Transcript(segments=(source,)),
        max_chars_per_cue=10,
    )

    assert len(cues) == 1
    assert (cues[0].start_ms, cues[0].end_ms) == (1_000, 5_000)
    assert cues[0].text == source.source_text


def test_wrapping_prefers_words_and_preserves_long_unbreakable_tokens() -> None:
    assert wrap_subtitle_text("alpha beta gamma delta", max_line_chars=12) == (
        "alpha beta",
        "gamma delta",
    )
    assert wrap_subtitle_text("unbreakable-token", max_line_chars=5) == ("unbreakable-token",)


def test_cue_construction_is_chronological_and_repeatable() -> None:
    transcript = Transcript(
        segments=(
            segment("s1", 100, 900, "First."),
            segment("s2", 1_000, 2_000, "Second."),
        )
    )

    first = build_subtitle_cues(transcript)
    second = build_subtitle_cues(transcript)

    assert first == second
    assert all(
        current.start_ms >= previous.end_ms
        for previous, current in zip(first, first[1:], strict=False)
    )
