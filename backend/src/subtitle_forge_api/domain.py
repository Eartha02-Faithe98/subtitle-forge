"""Canonical Phase 1 domain models with timestamp invariants."""

from enum import StrEnum
from pathlib import PurePath
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SourceType(StrEnum):
    YOUTUBE = "youtube"
    MP3 = "mp3"
    MP4 = "mp4"


class WhisperProfile(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    ACCURATE = "accurate"


class JobStage(StrEnum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_SUBTITLES = "GENERATING_SUBTITLES"
    GENERATING_SUMMARY = "GENERATING_SUMMARY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorCategory(StrEnum):
    INTAKE_INVALID = "intake_invalid"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MEDIA_INVALID = "media_invalid"
    DEPENDENCY_MISSING = "dependency_missing"
    WHISPER_UNAVAILABLE = "whisper_unavailable"
    OLLAMA_UNAVAILABLE = "ollama_unavailable"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    INTERRUPTED = "interrupted"
    UNEXPECTED = "unexpected"


class ArtifactKind(StrEnum):
    ENGLISH_TRANSCRIPT = "english_transcript"
    TRADITIONAL_CHINESE_TRANSCRIPT = "traditional_chinese_transcript"
    ENGLISH_SRT = "english_srt"
    TRADITIONAL_CHINESE_SRT = "traditional_chinese_srt"
    BILINGUAL_SRT = "bilingual_srt"
    ENGLISH_SUMMARY = "english_summary"
    TRADITIONAL_CHINESE_SUMMARY = "traditional_chinese_summary"


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class TimedModel(DomainModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.end_ms <= self.start_ms:
            raise ValueError("end time must be greater than start time")
        return self


class WordSegment(TimedModel):
    text: NonEmptyText


class TranscriptSegment(TimedModel):
    segment_id: NonEmptyText
    source_text: NonEmptyText
    language: Literal["en"] = "en"
    words: tuple[WordSegment, ...] = ()

    @model_validator(mode="after")
    def validate_words(self) -> Self:
        previous_end = self.start_ms
        for word in self.words:
            if word.start_ms < self.start_ms or word.end_ms > self.end_ms:
                raise ValueError("word timing must stay inside its transcript segment")
            if word.start_ms < previous_end:
                raise ValueError("word timings must be chronological")
            previous_end = word.end_ms
        return self


class TranslatedSegment(TimedModel):
    segment_id: NonEmptyText
    translated_text: NonEmptyText
    language: Literal["zh-TW"] = "zh-TW"


class Transcript(DomainModel):
    language: Literal["en"] = "en"
    segments: Annotated[tuple[TranscriptSegment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_segments(self) -> Self:
        identifiers = [segment.segment_id for segment in self.segments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate transcript segment identifier")
        if any(
            current.start_ms < previous.start_ms
            for previous, current in zip(self.segments, self.segments[1:], strict=False)
        ):
            raise ValueError("transcript segments must be chronological")
        return self


class TranslatedTranscript(DomainModel):
    language: Literal["zh-TW"] = "zh-TW"
    segments: Annotated[tuple[TranslatedSegment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_segments(self) -> Self:
        identifiers = [segment.segment_id for segment in self.segments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate translated segment identifier")
        return self


class Summary(DomainModel):
    language: Literal["en", "zh-TW"]
    text: NonEmptyText


class JobError(DomainModel):
    category: ErrorCategory
    stage: JobStage | None = None
    message: NonEmptyText


class ArtifactManifestEntry(DomainModel):
    artifact_key: NonEmptyText
    kind: ArtifactKind
    filename: NonEmptyText
    media_type: NonEmptyText
    size_bytes: int = Field(ge=0)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if PurePath(value).name != value or value in {".", ".."}:
            raise ValueError("artifact filename must not contain a path")
        return value
