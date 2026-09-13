import importlib.util
from pathlib import Path

import pytest

from subtitle_forge_api.domain import (
    ArtifactKind,
    ArtifactManifestEntry,
    ErrorCategory,
    JobError,
    JobStage,
    SourceType,
)


def load_persistence():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.persistence") is not None
    from subtitle_forge_api import persistence

    return persistence


def make_record(persistence, *, job_id: str = "job-1"):  # type: ignore[no-untyped-def]
    return persistence.JobRecord(
        job_id=job_id,
        source_type=SourceType.MP3,
        source_metadata={"display_name": "lesson.mp3"},
    )


def test_job_repository_persists_across_connections(tmp_path: Path) -> None:
    persistence = load_persistence()
    database = tmp_path / "jobs.sqlite3"
    first = persistence.SQLiteJobRepository(database)
    first.initialize()
    record = make_record(persistence)
    first.create(record)
    first.close()

    second = persistence.SQLiteJobRepository(database)
    second.initialize()

    assert second.get("job-1") == record
    second.close()


def test_duplicate_create_is_atomic_and_keeps_original(tmp_path: Path) -> None:
    persistence = load_persistence()
    repository = persistence.SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    original = make_record(persistence)
    repository.create(original)

    with pytest.raises(persistence.JobAlreadyExistsError):
        repository.create(
            original.model_copy(update={"source_metadata": {"display_name": "changed.mp3"}})
        )

    assert repository.get(original.job_id) == original
    repository.close()


def test_update_atomically_persists_progress_error_and_artifacts(tmp_path: Path) -> None:
    persistence = load_persistence()
    repository = persistence.SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    original = make_record(persistence)
    repository.create(original)
    artifact = ArtifactManifestEntry(
        artifact_key="english-srt",
        kind=ArtifactKind.ENGLISH_SRT,
        filename="lesson.en.srt",
        media_type="application/x-subrip",
        size_bytes=42,
    )
    updated = original.model_copy(
        update={
            "stage": JobStage.FAILED,
            "progress": 55,
            "error": JobError(
                category=ErrorCategory.OLLAMA_UNAVAILABLE,
                stage=JobStage.TRANSLATING,
                message="Start the configured local language model.",
            ),
            "artifacts": (artifact,),
        }
    )

    repository.update(updated)

    assert repository.get(original.job_id) == updated
    repository.close()


def test_update_rejects_unknown_job_without_creating_it(tmp_path: Path) -> None:
    persistence = load_persistence()
    repository = persistence.SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()

    with pytest.raises(persistence.JobNotFoundError):
        repository.update(make_record(persistence, job_id="missing"))

    assert repository.get("missing") is None
    repository.close()


def test_startup_recovery_fails_interrupted_jobs_and_preserves_completed_jobs(
    tmp_path: Path,
) -> None:
    persistence = load_persistence()
    from subtitle_forge_api.jobs import recover_on_startup

    database = tmp_path / "jobs.sqlite3"
    first = persistence.SQLiteJobRepository(database)
    first.initialize()
    interrupted = make_record(persistence, job_id="interrupted").model_copy(
        update={"stage": JobStage.TRANSCRIBING, "progress": 35}
    )
    artifact = ArtifactManifestEntry(
        artifact_key="english-srt",
        kind=ArtifactKind.ENGLISH_SRT,
        filename="lesson.en.srt",
        media_type="application/x-subrip",
        size_bytes=42,
    )
    completed = make_record(persistence, job_id="completed").model_copy(
        update={"stage": JobStage.COMPLETED, "progress": 100, "artifacts": (artifact,)}
    )
    first.create(interrupted)
    first.create(completed)
    first.close()

    restarted = persistence.SQLiteJobRepository(database)
    restarted.initialize()
    report = recover_on_startup(
        restarted,
        artifact_exists=lambda job_id, entry: (
            job_id == "completed" and entry.artifact_key == "english-srt"
        ),
    )

    recovered = restarted.get("interrupted")
    assert recovered is not None
    assert recovered.stage is JobStage.FAILED
    assert recovered.progress == 35
    assert recovered.error is not None
    assert recovered.error.category is ErrorCategory.INTERRUPTED
    assert restarted.get("completed") == completed
    assert report.interrupted_jobs == 1
    assert report.missing_artifacts == 0
    restarted.close()


def test_startup_recovery_reports_missing_completed_artifacts_without_regression(
    tmp_path: Path,
) -> None:
    persistence = load_persistence()
    from subtitle_forge_api.jobs import recover_on_startup

    repository = persistence.SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    artifact = ArtifactManifestEntry(
        artifact_key="english-srt",
        kind=ArtifactKind.ENGLISH_SRT,
        filename="missing.srt",
        media_type="application/x-subrip",
        size_bytes=42,
    )
    completed = make_record(persistence, job_id="completed").model_copy(
        update={"stage": JobStage.COMPLETED, "progress": 100, "artifacts": (artifact,)}
    )
    repository.create(completed)

    report = recover_on_startup(repository, artifact_exists=lambda _job, _entry: False)

    assert repository.get("completed") == completed
    assert report.interrupted_jobs == 0
    assert report.missing_artifacts == 1
    repository.close()
