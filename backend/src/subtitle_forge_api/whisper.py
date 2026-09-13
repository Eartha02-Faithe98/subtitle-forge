"""Local faster-whisper adapter producing canonical English transcripts."""

import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol, cast

from faster_whisper import WhisperModel  # type: ignore[import-untyped]
from pydantic import ValidationError

from subtitle_forge_api.domain import (
    Transcript,
    TranscriptSegment,
    WhisperProfile,
    WordSegment,
)
from subtitle_forge_api.providers import ProgressCallback


class WhisperUnavailableError(ValueError):
    """Safe Local Whisper failure suitable for user-facing guidance."""


class NoSpeechDetectedError(WhisperUnavailableError):
    """The bounded audio contains no recognizable English speech."""


class WhisperModelClient(Protocol):
    def transcribe(
        self,
        audio: str,
        **options: Any,
    ) -> tuple[Iterable[Any], object]: ...


class WhisperModelFactory(Protocol):
    def __call__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> WhisperModelClient: ...


class WhisperWordResult(Protocol):
    start: object
    end: object
    word: object


class WhisperSegmentResult(Protocol):
    start: object
    end: object
    text: object
    words: Iterable[WhisperWordResult] | None


def create_whisper_model(
    model_name: str,
    device: str,
    compute_type: str,
    local_files_only: bool,
) -> WhisperModelClient:
    return cast(
        WhisperModelClient,
        WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            local_files_only=local_files_only,
        ),
    )


class FasterWhisperProvider:
    def __init__(
        self,
        *,
        profile: WhisperProfile,
        model_map: Mapping[str, str],
        device: str = "cpu",
        compute_type: str = "int8",
        model_factory: WhisperModelFactory = create_whisper_model,
    ) -> None:
        try:
            model_name = model_map[profile.value]
        except KeyError as error:
            raise ValueError(f"No model is configured for profile {profile.value}") from error
        if not model_name.strip():
            raise ValueError("Whisper model name must not be empty")
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model_factory = model_factory

    def transcribe(
        self,
        audio_path: Path,
        progress: ProgressCallback | None = None,
    ) -> Transcript:
        if not audio_path.is_file():
            raise WhisperUnavailableError("Prepared audio is unavailable")
        report = progress or _ignore_progress
        report(0.0)
        try:
            model = self._model_factory(
                self._model_name,
                self._device,
                self._compute_type,
                True,
            )
        except Exception as error:
            raise WhisperUnavailableError(
                "The selected Whisper model is not available locally"
            ) from error

        try:
            raw_segments, info = model.transcribe(
                str(audio_path),
                language="en",
                word_timestamps=True,
                vad_filter=True,
            )
            duration_seconds = _positive_float(getattr(info, "duration", 0.0))
            normalized: list[TranscriptSegment] = []
            for raw in raw_segments:
                normalized.append(_normalize_segment(raw, len(normalized) + 1))
                if duration_seconds > 0:
                    report(min(1.0, normalized[-1].end_ms / (duration_seconds * 1_000)))
            normalized.sort(key=lambda item: (item.start_ms, item.end_ms))
            normalized = [
                item.model_copy(update={"segment_id": f"whisper-{index:06d}"})
                for index, item in enumerate(normalized, start=1)
            ]
            if not normalized:
                raise NoSpeechDetectedError("Local Whisper found no recognizable English speech")
            transcript = Transcript(segments=tuple(normalized))
        except WhisperUnavailableError:
            raise
        except (AttributeError, TypeError, ValueError, ValidationError) as error:
            raise WhisperUnavailableError(
                "Local Whisper returned invalid timestamped text"
            ) from error
        except Exception as error:
            raise WhisperUnavailableError(
                "Local Whisper could not transcribe this audio"
            ) from error

        report(1.0)
        return transcript


def _normalize_segment(raw: object, index: int) -> TranscriptSegment:
    segment = cast(WhisperSegmentResult, raw)
    start_ms = _seconds_to_ms(segment.start)
    end_ms = _seconds_to_ms(segment.end)
    text_value = segment.text
    if not isinstance(text_value, str):
        raise TypeError("segment text must be a string")

    raw_words = segment.words
    words: list[WordSegment] = []
    if raw_words is not None:
        for raw_word in raw_words:
            word_text = raw_word.word
            if not isinstance(word_text, str):
                raise TypeError("word text must be a string")
            if word_text.strip():
                words.append(
                    WordSegment(
                        start_ms=_seconds_to_ms(raw_word.start),
                        end_ms=_seconds_to_ms(raw_word.end),
                        text=word_text,
                    )
                )
    return TranscriptSegment(
        segment_id=f"whisper-{index:06d}",
        start_ms=start_ms,
        end_ms=end_ms,
        source_text=text_value,
        words=tuple(words),
    )


def _seconds_to_ms(value: object) -> int:
    if not isinstance(value, (int, float)):
        raise TypeError("timestamp must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("timestamp must be finite and non-negative")
    return round(numeric * 1_000)


def _positive_float(value: object) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric > 0 else 0.0


def _ignore_progress(value: float) -> None:
    del value
