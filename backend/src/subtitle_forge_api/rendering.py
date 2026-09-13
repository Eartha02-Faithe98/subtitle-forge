"""Deterministic plain-text transcript rendering from canonical segments."""

from subtitle_forge_api.domain import (
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.timestamps import format_display_timestamp


class ArtifactAlignmentError(ValueError):
    """English and translated canonical segments do not align exactly."""


def render_english_transcript(transcript: Transcript) -> str:
    return "".join(_line(segment.start_ms, segment.source_text) for segment in transcript.segments)


def render_traditional_chinese_transcript(
    transcript: Transcript,
    translated: TranslatedTranscript,
) -> str:
    return "".join(
        _line(source.start_ms, target.translated_text)
        for source, target in align_translations(transcript, translated)
    )


def align_translations(
    transcript: Transcript,
    translated: TranslatedTranscript,
) -> tuple[tuple[TranscriptSegment, TranslatedSegment], ...]:
    if len(transcript.segments) != len(translated.segments):
        raise ArtifactAlignmentError("Translated segments do not align with the English transcript")
    aligned: list[tuple[TranscriptSegment, TranslatedSegment]] = []
    for source, target in zip(
        transcript.segments,
        translated.segments,
        strict=True,
    ):
        if (
            source.segment_id != target.segment_id
            or source.start_ms != target.start_ms
            or source.end_ms != target.end_ms
        ):
            raise ArtifactAlignmentError(
                "Translated segments do not align with the English transcript"
            )
        aligned.append((source, target))
    return tuple(aligned)


def _line(start_ms: int, text: str) -> str:
    return f"[{format_display_timestamp(start_ms)}] {text}\n"
