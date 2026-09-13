from pathlib import Path

import pytest

from subtitle_forge_api.domain import ArtifactKind, ArtifactManifestEntry, JobStage, SourceType
from subtitle_forge_api.lifecycle import JobLifecycleService, completed_stages
from subtitle_forge_api.persistence import JobRecord, SQLiteJobRepository


def repository(tmp_path: Path) -> SQLiteJobRepository:
    result = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    result.initialize()
    return result


def artifacts() -> tuple[ArtifactManifestEntry, ...]:
    return tuple(
        ArtifactManifestEntry(
            artifact_key=kind.value,
            kind=kind,
            filename=f"{kind.value}.txt",
            media_type="text/plain; charset=utf-8",
            size_bytes=10,
        )
        for kind in ArtifactKind
    )


def test_progress_is_persisted_clamped_and_monotonic(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    record = JobRecord(job_id="job-1", source_type=SourceType.MP3)
    repo.create(record)
    lifecycle = JobLifecycleService(repo)

    extracting = lifecycle.report("job-1", JobStage.EXTRACTING_AUDIO, -1.0)
    half_transcribed = lifecycle.report("job-1", JobStage.TRANSCRIBING, 0.5)
    stale_callback = lifecycle.report("job-1", JobStage.TRANSCRIBING, 0.2)
    overcomplete = lifecycle.report("job-1", JobStage.TRANSCRIBING, 2.0)

    assert extracting.progress == 10
    assert half_transcribed.progress == 38
    assert stale_callback.progress == 38
    assert overcomplete.progress == 55
    assert repo.get("job-1") == overcomplete
    repo.close()


@pytest.mark.parametrize(
    ("source_type", "stage", "expected"),
    [
        (SourceType.MP3, JobStage.TRANSLATING, (JobStage.EXTRACTING_AUDIO, JobStage.TRANSCRIBING)),
        (
            SourceType.YOUTUBE,
            JobStage.TRANSLATING,
            (JobStage.DOWNLOADING, JobStage.EXTRACTING_AUDIO, JobStage.TRANSCRIBING),
        ),
    ],
)
def test_completed_stages_reflect_only_the_applicable_source_path(
    source_type: SourceType,
    stage: JobStage,
    expected: tuple[JobStage, ...],
) -> None:
    assert (
        completed_stages(JobRecord(job_id="job", source_type=source_type, stage=stage)) == expected
    )


def test_completion_requires_artifacts_and_manifest_guard_before_100(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    repo.create(
        JobRecord(
            job_id="job-2",
            source_type=SourceType.MP4,
            stage=JobStage.GENERATING_SUMMARY,
            progress=95,
        )
    )
    guard_calls: list[tuple[ArtifactManifestEntry, ...]] = []

    def guard(record: JobRecord) -> None:
        guard_calls.append(record.artifacts)
        if len(record.artifacts) != 7:
            raise ValueError("manifest incomplete")

    lifecycle = JobLifecycleService(repo, completion_guard=guard)
    with pytest.raises(ValueError, match="manifest incomplete"):
        lifecycle.report("job-2", JobStage.COMPLETED)
    assert repo.get("job-2").progress == 95  # type: ignore[union-attr]

    completed = lifecycle.report("job-2", JobStage.COMPLETED, artifacts=artifacts())
    assert completed.progress == 100
    assert completed.stage is JobStage.COMPLETED
    assert len(completed.artifacts) == 7
    assert len(guard_calls) == 2
    repo.close()


def test_invalid_skipped_and_backward_transitions_are_not_persisted(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    original = JobRecord(job_id="job-3", source_type=SourceType.MP3)
    repo.create(original)
    lifecycle = JobLifecycleService(repo)
    with pytest.raises(ValueError, match="transition"):
        lifecycle.report("job-3", JobStage.DOWNLOADING)
    assert repo.get("job-3") == original
    repo.close()
