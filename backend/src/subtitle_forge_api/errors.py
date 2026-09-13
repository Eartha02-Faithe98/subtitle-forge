"""Stable safe error classification for persisted job failures."""

from datetime import UTC, datetime

from subtitle_forge_api.artifacts import ArtifactPublicationError
from subtitle_forge_api.domain import ErrorCategory, JobError, JobStage
from subtitle_forge_api.intake import UploadValidationError
from subtitle_forge_api.jobs import ensure_transition
from subtitle_forge_api.media import AudioExtractionError, MediaInspectionError
from subtitle_forge_api.ollama import OllamaUnavailableError
from subtitle_forge_api.persistence import JobNotFoundError, JobRecord, JobRepository
from subtitle_forge_api.summarization import SummaryValidationError
from subtitle_forge_api.translation import TranslationValidationError
from subtitle_forge_api.whisper import WhisperUnavailableError
from subtitle_forge_api.youtube import YouTubeAcquisitionError


class DependencyMissingError(RuntimeError):
    """A required local executable or runtime is unavailable."""


class InterruptedProcessingError(RuntimeError):
    """Processing stopped because the local application shut down."""


_MESSAGES = {
    ErrorCategory.INTAKE_INVALID: "Check the selected input and try again.",
    ErrorCategory.SOURCE_UNAVAILABLE: "The public YouTube source could not be acquired.",
    ErrorCategory.MEDIA_INVALID: "The media file could not be read or prepared.",
    ErrorCategory.DEPENDENCY_MISSING: ("A required local processing dependency is unavailable."),
    ErrorCategory.WHISPER_UNAVAILABLE: "Local Whisper could not process this audio.",
    ErrorCategory.OLLAMA_UNAVAILABLE: ("The local translation or summary service is unavailable."),
    ErrorCategory.ARTIFACT_UNAVAILABLE: ("The requested output files could not be completed."),
    ErrorCategory.INTERRUPTED: "Processing was interrupted by an application restart.",
    ErrorCategory.UNEXPECTED: "Processing stopped because of an unexpected local error.",
}


class SafeJobFailureService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def fail(self, job_id: str, error: Exception) -> JobRecord:
        record = self._repository.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        ensure_transition(record.stage, JobStage.FAILED, record.source_type)
        category = classify_error(error)
        failed = record.model_copy(
            update={
                "stage": JobStage.FAILED,
                "error": JobError(
                    category=category,
                    stage=record.stage,
                    message=_MESSAGES[category],
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self._repository.update(failed)
        return failed


def classify_error(error: Exception) -> ErrorCategory:
    if isinstance(error, UploadValidationError):
        return ErrorCategory.INTAKE_INVALID
    if isinstance(error, YouTubeAcquisitionError):
        return ErrorCategory.SOURCE_UNAVAILABLE
    if isinstance(error, (MediaInspectionError, AudioExtractionError)):
        return ErrorCategory.MEDIA_INVALID
    if isinstance(error, DependencyMissingError):
        return ErrorCategory.DEPENDENCY_MISSING
    if isinstance(error, WhisperUnavailableError):
        return ErrorCategory.WHISPER_UNAVAILABLE
    if isinstance(
        error,
        (OllamaUnavailableError, TranslationValidationError, SummaryValidationError),
    ):
        return ErrorCategory.OLLAMA_UNAVAILABLE
    if isinstance(error, ArtifactPublicationError):
        return ErrorCategory.ARTIFACT_UNAVAILABLE
    if isinstance(error, InterruptedProcessingError):
        return ErrorCategory.INTERRUPTED
    return ErrorCategory.UNEXPECTED
