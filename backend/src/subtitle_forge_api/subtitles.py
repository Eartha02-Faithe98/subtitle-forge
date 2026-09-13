"""Deterministic subtitle cue construction from canonical English timings."""

from dataclasses import dataclass

from subtitle_forge_api.domain import Transcript, TranscriptSegment, WordSegment

_SENTENCE_ENDINGS = (".", "?", "!", "。", "？", "！")
_ATTACHED_PUNCTUATION = tuple(",.!?:;)]}%，。！？：；、」』】》）％")


@dataclass(frozen=True)
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str
    segment_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("subtitle cue must have a positive interval")
        if not self.text.strip() or not self.segment_ids:
            raise ValueError("subtitle cue text and segment IDs must not be empty")


def build_subtitle_cues(
    transcript: Transcript,
    *,
    max_chars_per_cue: int = 84,
    max_duration_ms: int = 7_000,
    merge_gap_ms: int = 250,
) -> tuple[SubtitleCue, ...]:
    if max_chars_per_cue < 1 or max_duration_ms < 1 or merge_gap_ms < 0:
        raise ValueError("subtitle reading constraints must be positive")

    candidates: list[SubtitleCue] = []
    for segment in transcript.segments:
        candidates.extend(_split_segment(segment, max_chars_per_cue))

    merged: list[SubtitleCue] = []
    for candidate in candidates:
        if merged and _can_merge(
            merged[-1],
            candidate,
            max_chars_per_cue,
            max_duration_ms,
            merge_gap_ms,
        ):
            previous = merged.pop()
            merged.append(
                SubtitleCue(
                    start_ms=previous.start_ms,
                    end_ms=candidate.end_ms,
                    text=_join_text(previous.text, candidate.text),
                    segment_ids=previous.segment_ids + candidate.segment_ids,
                )
            )
        else:
            merged.append(candidate)
    return tuple(merged)


def wrap_subtitle_text(
    text: str,
    *,
    max_line_chars: int = 42,
) -> tuple[str, ...]:
    if max_line_chars < 1:
        raise ValueError("max_line_chars must be positive")
    tokens = text.split()
    if not tokens:
        raise ValueError("subtitle text must not be empty")
    lines: list[str] = []
    current = ""
    for token in tokens:
        proposed = _join_text(current, token) if current else token
        if current and len(proposed) > max_line_chars:
            lines.append(current)
            current = token
        else:
            current = proposed
    lines.append(current)
    return tuple(lines)


def _split_segment(
    segment: TranscriptSegment,
    max_chars: int,
) -> list[SubtitleCue]:
    if len(segment.source_text) <= max_chars or not segment.words:
        return [
            SubtitleCue(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.source_text,
                segment_ids=(segment.segment_id,),
            )
        ]

    groups: list[list[WordSegment]] = []
    current: list[WordSegment] = []
    current_text = ""
    for word in segment.words:
        proposed = _join_text(current_text, word.text) if current else word.text
        if current and len(proposed) > max_chars:
            groups.append(current)
            current = []
            current_text = ""
        current.append(word)
        current_text = _join_text(current_text, word.text) if current_text else word.text
    if current:
        groups.append(current)

    return [
        SubtitleCue(
            start_ms=group[0].start_ms,
            end_ms=group[-1].end_ms,
            text=_words_text(group),
            segment_ids=(segment.segment_id,),
        )
        for group in groups
    ]


def _can_merge(
    previous: SubtitleCue,
    current: SubtitleCue,
    max_chars: int,
    max_duration_ms: int,
    merge_gap_ms: int,
) -> bool:
    if set(previous.segment_ids) & set(current.segment_ids):
        return False
    if previous.text.rstrip().endswith(_SENTENCE_ENDINGS):
        return False
    if current.start_ms < previous.end_ms:
        return False
    if current.start_ms - previous.end_ms > merge_gap_ms:
        return False
    combined = _join_text(previous.text, current.text)
    return len(combined) <= max_chars and current.end_ms - previous.start_ms <= max_duration_ms


def _words_text(words: list[WordSegment]) -> str:
    text = ""
    for word in words:
        text = _join_text(text, word.text) if text else word.text
    return text


def _join_text(left: str, right: str) -> str:
    right = right.strip()
    if not left:
        return right
    separator = "" if right.startswith(_ATTACHED_PUNCTUATION) else " "
    return f"{left.rstrip()}{separator}{right}"
