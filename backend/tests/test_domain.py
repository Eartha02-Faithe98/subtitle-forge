import importlib.util

import pytest
from pydantic import ValidationError


def load_domain():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.domain") is not None
    from subtitle_forge_api import domain

    return domain


def test_phase_one_domain_models_capture_timestamped_bilingual_results() -> None:
    domain = load_domain()
    word = domain.WordSegment(start_ms=0, end_ms=450, text="Hello")
    source = domain.TranscriptSegment(
        segment_id="segment-1",
        start_ms=0,
        end_ms=1_000,
        source_text="Hello world.",
        language="en",
        words=(word,),
    )
    translation = domain.TranslatedSegment(
        segment_id="segment-1",
        start_ms=0,
        end_ms=1_000,
        translated_text="哈囉，世界。",
        language="zh-TW",
    )

    transcript = domain.Transcript(language="en", segments=(source,))
    translated = domain.TranslatedTranscript(language="zh-TW", segments=(translation,))
    summary = domain.Summary(language="zh-TW", text="這是一段摘要。")
    error = domain.JobError(
        category=domain.ErrorCategory.MEDIA_INVALID,
        stage=domain.JobStage.EXTRACTING_AUDIO,
        message="Unable to extract audio from this media.",
    )
    artifact = domain.ArtifactManifestEntry(
        artifact_key="english-srt",
        kind=domain.ArtifactKind.ENGLISH_SRT,
        filename="subtitle-forge-english.srt",
        media_type="application/x-subrip",
        size_bytes=128,
    )

    assert transcript.segments[0].words == (word,)
    assert translated.segments[0].segment_id == source.segment_id
    assert summary.text == "這是一段摘要。"
    assert error.stage is domain.JobStage.EXTRACTING_AUDIO
    assert artifact.kind is domain.ArtifactKind.ENGLISH_SRT


@pytest.mark.parametrize(
    "segment",
    [
        {"segment_id": "s1", "start_ms": -1, "end_ms": 1, "source_text": "text"},
        {"segment_id": "s1", "start_ms": 2, "end_ms": 1, "source_text": "text"},
        {"segment_id": "s1", "start_ms": 0, "end_ms": 1, "source_text": " "},
        {
            "segment_id": "s1",
            "start_ms": 0,
            "end_ms": 1,
            "source_text": "text",
            "language": "fr",
        },
    ],
)
def test_transcript_segment_rejects_invalid_values(segment: dict[str, object]) -> None:
    domain = load_domain()

    with pytest.raises(ValidationError):
        domain.TranscriptSegment(**segment)


def test_transcript_rejects_duplicate_segment_ids() -> None:
    domain = load_domain()
    first = domain.TranscriptSegment(
        segment_id="duplicate", start_ms=0, end_ms=1_000, source_text="One"
    )
    second = domain.TranscriptSegment(
        segment_id="duplicate", start_ms=1_000, end_ms=2_000, source_text="Two"
    )

    with pytest.raises(ValidationError, match="duplicate"):
        domain.Transcript(language="en", segments=(first, second))


def test_word_and_translation_must_stay_inside_source_timing_contract() -> None:
    domain = load_domain()

    with pytest.raises(ValidationError):
        domain.WordSegment(start_ms=10, end_ms=5, text="word")
    with pytest.raises(ValidationError):
        domain.TranslatedSegment(
            segment_id="s1",
            start_ms=0,
            end_ms=100,
            translated_text="",
            language="zh-TW",
        )


@pytest.mark.parametrize("language", ["fr", "zh-CN", ""])
def test_summary_rejects_unsupported_languages(language: str) -> None:
    domain = load_domain()

    with pytest.raises(ValidationError):
        domain.Summary(language=language, text="Summary")
