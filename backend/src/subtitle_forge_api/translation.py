"""Strictly aligned Traditional Chinese translation over local Ollama."""

import json
from collections.abc import Mapping
from typing import Any, Protocol

from subtitle_forge_api.domain import (
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)

_TRANSLATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "translated_text": {"type": "string"},
                },
                "required": ["id", "translated_text"],
            },
        }
    },
    "required": ["segments"],
}


class StructuredGenerationClient(Protocol):
    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, object],
    ) -> dict[str, Any]: ...


class TranslationValidationError(ValueError):
    """The local model did not preserve exact segment alignment."""


class OllamaTranslationProvider:
    def __init__(
        self,
        *,
        client: StructuredGenerationClient,
        max_batch_chars: int = 4_000,
    ) -> None:
        if max_batch_chars < 1:
            raise ValueError("max_batch_chars must be positive")
        self._client = client
        self._max_batch_chars = max_batch_chars

    def translate(self, transcript: Transcript) -> TranslatedTranscript:
        translated: list[TranslatedSegment] = []
        for batch in _make_batches(transcript.segments, self._max_batch_chars):
            values = self._translate_batch(batch)
            translated.extend(
                TranslatedSegment(
                    segment_id=source.segment_id,
                    start_ms=source.start_ms,
                    end_ms=source.end_ms,
                    translated_text=text,
                )
                for source, text in zip(batch, values, strict=True)
            )
        return TranslatedTranscript(segments=tuple(translated))

    def _translate_batch(
        self,
        batch: tuple[TranscriptSegment, ...],
    ) -> tuple[str, ...]:
        prompt = _translation_prompt(batch)
        response = self._client.generate_json(prompt, _TRANSLATION_SCHEMA)
        try:
            return _validate_alignment(response, batch)
        except TranslationValidationError:
            repair_prompt = (
                "Repair the previous translation response. Return only the exact JSON "
                "schema, in the exact requested segment ID order, with no missing, "
                "duplicate, extra, or empty Traditional Chinese values.\n\n"
                f"{prompt}"
            )
            repaired = self._client.generate_json(
                repair_prompt,
                _TRANSLATION_SCHEMA,
            )
            try:
                return _validate_alignment(repaired, batch)
            except TranslationValidationError as error:
                raise TranslationValidationError(
                    "Traditional Chinese translation could not align with source segments"
                ) from error


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
            raise TranslationValidationError(
                "A source segment exceeds the configured translation batch limit"
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


def _translation_prompt(batch: tuple[TranscriptSegment, ...]) -> str:
    payload = [{"id": segment.segment_id, "source_text": segment.source_text} for segment in batch]
    return (
        "Translate every source_text into natural Traditional Chinese (zh-TW). "
        "Preserve each id exactly and keep the same order. Return JSON only.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _validate_alignment(
    response: dict[str, Any],
    batch: tuple[TranscriptSegment, ...],
) -> tuple[str, ...]:
    if set(response) != {"segments"}:
        raise TranslationValidationError("Translation response has invalid fields")
    items = response.get("segments")
    if not isinstance(items, list) or len(items) != len(batch):
        raise TranslationValidationError("Translation response does not align")

    translated: list[str] = []
    for item, source in zip(items, batch, strict=True):
        if not isinstance(item, dict) or set(item) != {"id", "translated_text"}:
            raise TranslationValidationError("Translation item has invalid fields")
        identifier = item.get("id")
        text = item.get("translated_text")
        if identifier != source.segment_id or not isinstance(text, str) or not text.strip():
            raise TranslationValidationError("Translation item does not align")
        translated.append(text.strip())
    return tuple(translated)
