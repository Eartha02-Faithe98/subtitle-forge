"""Plain English and Traditional Chinese summaries via bounded map-reduce."""

import json
from typing import Any

from subtitle_forge_api.domain import Summary, Transcript, TranscriptSegment
from subtitle_forge_api.providers import SummaryLanguage
from subtitle_forge_api.translation import StructuredGenerationClient

_SUMMARY_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}


class SummaryValidationError(ValueError):
    """The local model did not return one plain non-empty summary."""


class OllamaSummaryProvider:
    def __init__(
        self,
        *,
        client: StructuredGenerationClient,
        max_batch_chars: int = 4_000,
        max_reduce_chars: int = 12_000,
    ) -> None:
        if max_batch_chars < 1 or max_reduce_chars < 1:
            raise ValueError("summary character limits must be positive")
        self._client = client
        self._max_batch_chars = max_batch_chars
        self._max_reduce_chars = max_reduce_chars

    def summarize(
        self,
        transcript: Transcript,
        language: SummaryLanguage,
    ) -> Summary:
        batches = _make_batches(transcript.segments, self._max_batch_chars)
        if len(batches) == 1:
            text = self._generate(_direct_prompt(batches[0], language))
        else:
            partials = [self._generate(_map_prompt(batch, language)) for batch in batches]
            text = self._reduce(partials, language)
        return Summary(language=language, text=text)

    def _reduce(self, partials: list[str], language: SummaryLanguage) -> str:
        current = partials
        while len(current) > 1:
            groups = _group_partials(current, self._max_reduce_chars)
            if len(groups) == len(current):
                raise SummaryValidationError(
                    "Partial summaries exceed the configured reduction limit"
                )
            current = [self._generate(_reduce_prompt(group, language)) for group in groups]
        return current[0]

    def _generate(self, prompt: str) -> str:
        response = self._client.generate_json(prompt, _SUMMARY_SCHEMA)
        if set(response) != {"summary"}:
            raise SummaryValidationError("Local provider returned an invalid summary")
        text: Any = response.get("summary")
        if not isinstance(text, str) or not text.strip():
            raise SummaryValidationError("Local provider returned an empty summary")
        return text.strip()


def _make_batches(
    segments: tuple[TranscriptSegment, ...],
    max_chars: int,
) -> tuple[tuple[TranscriptSegment, ...], ...]:
    batches: list[tuple[TranscriptSegment, ...]] = []
    current: list[TranscriptSegment] = []
    current_chars = 0
    for segment in segments:
        segment_chars = len(segment.source_text)
        if segment_chars > max_chars:
            raise SummaryValidationError(
                "A transcript segment exceeds the configured summary batch limit"
            )
        if current and current_chars + segment_chars > max_chars:
            batches.append(tuple(current))
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += segment_chars
    if current:
        batches.append(tuple(current))
    return tuple(batches)


def _group_partials(partials: list[str], max_chars: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for partial in partials:
        if len(partial) > max_chars:
            raise SummaryValidationError("A partial summary exceeds the configured reduction limit")
        if current and current_chars + len(partial) > max_chars:
            groups.append(current)
            current = []
            current_chars = 0
        current.append(partial)
        current_chars += len(partial)
    if current:
        groups.append(current)
    return groups


def _instruction(language: SummaryLanguage) -> str:
    language_name = "English" if language == "en" else "Traditional Chinese (zh-TW)"
    return (
        f"Write one concise plain-text summary in {language_name}. "
        "Do not add chapters, key-point metadata, timestamps, or timestamp citations. "
        "Return JSON only."
    )


def _source_text(batch: tuple[TranscriptSegment, ...]) -> str:
    return "\n".join(segment.source_text for segment in batch)


def _direct_prompt(
    batch: tuple[TranscriptSegment, ...],
    language: SummaryLanguage,
) -> str:
    return f"{_instruction(language)}\n\nTranscript:\n{_source_text(batch)}"


def _map_prompt(
    batch: tuple[TranscriptSegment, ...],
    language: SummaryLanguage,
) -> str:
    return f"{_instruction(language)}\n\nTranscript part:\n{_source_text(batch)}"


def _reduce_prompt(partials: list[str], language: SummaryLanguage) -> str:
    encoded = json.dumps(partials, ensure_ascii=False, separators=(",", ":"))
    return f"{_instruction(language)}\n\nCombine these partial summaries:\n{encoded}"
