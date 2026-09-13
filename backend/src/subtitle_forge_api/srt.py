"""Deterministic UTF-8 SRT rendering for English, zh-TW, and bilingual output."""

from subtitle_forge_api.domain import Transcript, TranslatedTranscript
from subtitle_forge_api.rendering import align_translations
from subtitle_forge_api.subtitles import SubtitleCue, wrap_subtitle_text
from subtitle_forge_api.timestamps import format_srt_timestamp


def render_english_srt(cues: tuple[SubtitleCue, ...]) -> str:
    _validate_cue_order(cues)
    return "".join(
        _block(
            index,
            cue.start_ms,
            cue.end_ms,
            wrap_subtitle_text(cue.text),
        )
        for index, cue in enumerate(cues, start=1)
    )


def render_traditional_chinese_srt(
    transcript: Transcript,
    translated: TranslatedTranscript,
) -> str:
    return "".join(
        _block(
            index,
            source.start_ms,
            source.end_ms,
            wrap_subtitle_text(target.translated_text),
        )
        for index, (source, target) in enumerate(
            align_translations(transcript, translated),
            start=1,
        )
    )


def render_bilingual_srt(
    transcript: Transcript,
    translated: TranslatedTranscript,
) -> str:
    return "".join(
        _block(
            index,
            source.start_ms,
            source.end_ms,
            wrap_subtitle_text(source.source_text) + wrap_subtitle_text(target.translated_text),
        )
        for index, (source, target) in enumerate(
            align_translations(transcript, translated),
            start=1,
        )
    )


def _block(
    index: int,
    start_ms: int,
    end_ms: int,
    lines: tuple[str, ...],
) -> str:
    timecode = f"{format_srt_timestamp(start_ms)} --> {format_srt_timestamp(end_ms)}"
    body = "\n".join(lines)
    return f"{index}\n{timecode}\n{body}\n\n"


def _validate_cue_order(cues: tuple[SubtitleCue, ...]) -> None:
    if any(
        current.start_ms < previous.start_ms
        for previous, current in zip(cues, cues[1:], strict=False)
    ):
        raise ValueError("subtitle cues must be chronological")
