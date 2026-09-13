"""Atomic publication and completion validation for seven Phase 1 artifacts."""

from dataclasses import dataclass
from typing import Literal, Self
from uuid import UUID

from pydantic import model_validator

from subtitle_forge_api.domain import (
    ArtifactKind,
    ArtifactManifestEntry,
    DomainModel,
    Summary,
    Transcript,
    TranslatedTranscript,
)
from subtitle_forge_api.rendering import (
    align_translations,
    render_english_transcript,
    render_traditional_chinese_transcript,
)
from subtitle_forge_api.srt import (
    render_bilingual_srt,
    render_english_srt,
    render_traditional_chinese_srt,
)
from subtitle_forge_api.storage import ManagedJobStorage
from subtitle_forge_api.subtitles import build_subtitle_cues
from subtitle_forge_api.summary_artifacts import render_summary_artifact


class ArtifactPublicationError(ValueError):
    """Artifacts are incomplete or cannot be safely published."""


class Phase1Result(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    transcript: Transcript
    translated: TranslatedTranscript
    summaries: tuple[Summary, Summary]
    artifacts: tuple[ArtifactManifestEntry, ...]

    @model_validator(mode="after")
    def validate_complete_result(self) -> Self:
        try:
            parsed_job_id = UUID(self.job_id)
        except ValueError as error:
            raise ValueError("result job ID must be a UUID") from error
        if str(parsed_job_id) != self.job_id:
            raise ValueError("result job ID must use canonical UUID form")
        if {summary.language for summary in self.summaries} != {"en", "zh-TW"}:
            raise ValueError("result must contain one summary per output language")
        if len(self.artifacts) != len(ArtifactKind):
            raise ValueError("result must contain exactly seven artifacts")
        if {entry.kind for entry in self.artifacts} != set(ArtifactKind):
            raise ValueError("result must contain every required artifact kind")
        if len({entry.artifact_key for entry in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact keys must be unique")
        if len({entry.filename for entry in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact filenames must be unique")
        align_translations(self.transcript, self.translated)
        return self


@dataclass(frozen=True)
class _ArtifactPayload:
    kind: ArtifactKind
    filename: str
    media_type: str
    content: bytes


class ArtifactPublisher:
    def __init__(self, storage: ManagedJobStorage) -> None:
        self._storage = storage

    def publish(
        self,
        *,
        job_id: str,
        transcript: Transcript,
        translated: TranslatedTranscript,
        english_summary: Summary,
        chinese_summary: Summary,
    ) -> Phase1Result:
        payloads = _payloads(
            transcript,
            translated,
            english_summary,
            chinese_summary,
        )
        filenames = [payload.filename for payload in payloads]
        entries: list[ArtifactManifestEntry] = []
        try:
            for payload in payloads:
                path = self._storage.write_atomic(
                    job_id,
                    payload.filename,
                    payload.content,
                )
                entries.append(
                    ArtifactManifestEntry(
                        artifact_key=payload.kind.value,
                        kind=payload.kind,
                        filename=payload.filename,
                        media_type=payload.media_type,
                        size_bytes=path.stat().st_size,
                    )
                )
            result = Phase1Result(
                job_id=job_id,
                transcript=transcript,
                translated=translated,
                summaries=(english_summary, chinese_summary),
                artifacts=tuple(entries),
            )
            serialized = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
            self._storage.write_atomic(job_id, "result.json", serialized)
            assert_ready_for_completion(self._storage, result)
            return result
        except Exception as error:
            self._storage.cleanup_disposable(
                job_id,
                (*filenames, "result.json"),
            )
            if isinstance(error, ArtifactPublicationError):
                raise
            raise ArtifactPublicationError(
                "Could not publish the complete Phase 1 artifact set"
            ) from error


def assert_ready_for_completion(
    storage: ManagedJobStorage,
    result: Phase1Result,
) -> None:
    try:
        for entry in result.artifacts:
            path = storage.resolve_member(result.job_id, entry.filename)
            if (
                not path.is_file()
                or entry.size_bytes <= 0
                or path.stat().st_size != entry.size_bytes
            ):
                raise ArtifactPublicationError(
                    "Job cannot complete because an artifact is unavailable"
                )
        result_path = storage.resolve_member(result.job_id, "result.json")
        if not result_path.is_file():
            raise ArtifactPublicationError("Job cannot complete without its result manifest")
        persisted = Phase1Result.model_validate_json(result_path.read_bytes())
        if persisted != result:
            raise ArtifactPublicationError(
                "Job cannot complete with an inconsistent result manifest"
            )
    except ArtifactPublicationError:
        raise
    except Exception as error:
        raise ArtifactPublicationError(
            "Job cannot complete because artifact validation failed"
        ) from error


def _payloads(
    transcript: Transcript,
    translated: TranslatedTranscript,
    english_summary: Summary,
    chinese_summary: Summary,
) -> tuple[_ArtifactPayload, ...]:
    if english_summary.language != "en" or chinese_summary.language != "zh-TW":
        raise ArtifactPublicationError("Summary languages do not match their artifacts")
    english_markdown = render_summary_artifact(english_summary)
    chinese_markdown = render_summary_artifact(chinese_summary)
    cues = build_subtitle_cues(transcript)
    text_media = "text/plain; charset=utf-8"
    srt_media = "application/x-subrip; charset=utf-8"
    return (
        _ArtifactPayload(
            ArtifactKind.ENGLISH_TRANSCRIPT,
            "transcript-en.txt",
            text_media,
            render_english_transcript(transcript).encode("utf-8"),
        ),
        _ArtifactPayload(
            ArtifactKind.TRADITIONAL_CHINESE_TRANSCRIPT,
            "transcript-zh-TW.txt",
            text_media,
            render_traditional_chinese_transcript(transcript, translated).encode("utf-8"),
        ),
        _ArtifactPayload(
            ArtifactKind.ENGLISH_SRT,
            "subtitles-en.srt",
            srt_media,
            render_english_srt(cues).encode("utf-8"),
        ),
        _ArtifactPayload(
            ArtifactKind.TRADITIONAL_CHINESE_SRT,
            "subtitles-zh-TW.srt",
            srt_media,
            render_traditional_chinese_srt(transcript, translated).encode("utf-8"),
        ),
        _ArtifactPayload(
            ArtifactKind.BILINGUAL_SRT,
            "subtitles-bilingual.srt",
            srt_media,
            render_bilingual_srt(transcript, translated).encode("utf-8"),
        ),
        _ArtifactPayload(
            ArtifactKind.ENGLISH_SUMMARY,
            english_markdown.filename,
            english_markdown.media_type,
            english_markdown.content,
        ),
        _ArtifactPayload(
            ArtifactKind.TRADITIONAL_CHINESE_SUMMARY,
            chinese_markdown.filename,
            chinese_markdown.media_type,
            chinese_markdown.content,
        ),
    )
