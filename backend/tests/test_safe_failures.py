from pathlib import Path

import pytest

from subtitle_forge_api.artifacts import ArtifactPublicationError
from subtitle_forge_api.domain import ErrorCategory, JobStage, SourceType
from subtitle_forge_api.errors import DependencyMissingError, SafeJobFailureService
from subtitle_forge_api.intake import UploadValidationError
from subtitle_forge_api.media import MediaInspectionError
from subtitle_forge_api.ollama import OllamaUnavailableError
from subtitle_forge_api.persistence import JobRecord, SQLiteJobRepository
from subtitle_forge_api.whisper import WhisperUnavailableError
from subtitle_forge_api.youtube import YouTubeAcquisitionError


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (UploadValidationError("token=secret C:\\private"), ErrorCategory.INTAKE_INVALID),
        (YouTubeAcquisitionError("https://user:pass@example"), ErrorCategory.SOURCE_UNAVAILABLE),
        (MediaInspectionError("ffprobe C:\\private"), ErrorCategory.MEDIA_INVALID),
        (DependencyMissingError("C:\\private\\ffmpeg"), ErrorCategory.DEPENDENCY_MISSING),
        (WhisperUnavailableError("prompt and model path"), ErrorCategory.WHISPER_UNAVAILABLE),
        (OllamaUnavailableError("raw response token=secret"), ErrorCategory.OLLAMA_UNAVAILABLE),
        (ArtifactPublicationError("C:\\private\\result.json"), ErrorCategory.ARTIFACT_UNAVAILABLE),
        (RuntimeError("stack trace token=secret C:\\private"), ErrorCategory.UNEXPECTED),
    ],
)
def test_failures_use_stable_categories_and_never_persist_raw_diagnostics(
    tmp_path: Path,
    error: Exception,
    category: ErrorCategory,
) -> None:
    repository = SQLiteJobRepository(tmp_path / f"{category.value}.sqlite3")
    repository.initialize()
    repository.create(
        JobRecord(
            job_id="job-1",
            source_type=SourceType.MP4,
            stage=JobStage.TRANSCRIBING,
            progress=42,
        )
    )

    failed = SafeJobFailureService(repository).fail("job-1", error)

    assert failed.stage is JobStage.FAILED
    assert failed.progress == 42
    assert failed.error is not None
    assert failed.error.category is category
    assert failed.error.stage is JobStage.TRANSCRIBING
    serialized = failed.error.model_dump_json().lower()
    for secret in ("token", "secret", "c:\\private", "stack trace", "raw response", "prompt"):
        assert secret not in serialized
    assert repository.get("job-1") == failed
    repository.close()


def test_terminal_job_cannot_be_rewritten_as_failed(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    completed = JobRecord(
        job_id="job-2",
        source_type=SourceType.MP3,
        stage=JobStage.COMPLETED,
        progress=100,
    )
    repository.create(completed)

    with pytest.raises(ValueError, match="terminal"):
        SafeJobFailureService(repository).fail("job-2", RuntimeError("late"))

    assert repository.get("job-2") == completed
    repository.close()
