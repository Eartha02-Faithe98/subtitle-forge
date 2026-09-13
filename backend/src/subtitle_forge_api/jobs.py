"""Explicit local job transitions and stage progress ranges."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from subtitle_forge_api.domain import (
    ArtifactManifestEntry,
    ErrorCategory,
    JobError,
    JobStage,
    SourceType,
)
from subtitle_forge_api.persistence import JobRepository

_UPLOAD_PATH = (
    JobStage.PENDING,
    JobStage.EXTRACTING_AUDIO,
    JobStage.TRANSCRIBING,
    JobStage.TRANSLATING,
    JobStage.GENERATING_SUBTITLES,
    JobStage.GENERATING_SUMMARY,
    JobStage.COMPLETED,
)
_YOUTUBE_PATH = (
    JobStage.PENDING,
    JobStage.DOWNLOADING,
    *_UPLOAD_PATH[1:],
)
_TERMINAL_STAGES = {JobStage.COMPLETED, JobStage.FAILED}
_NON_TERMINAL_STAGES = tuple(stage for stage in JobStage if stage not in _TERMINAL_STAGES)
_PROGRESS_RANGES = {
    JobStage.PENDING: (0, 0),
    JobStage.DOWNLOADING: (1, 10),
    JobStage.EXTRACTING_AUDIO: (10, 20),
    JobStage.TRANSCRIBING: (20, 55),
    JobStage.TRANSLATING: (55, 70),
    JobStage.GENERATING_SUBTITLES: (70, 82),
    JobStage.GENERATING_SUMMARY: (82, 95),
    JobStage.COMPLETED: (100, 100),
}


def success_path(source_type: SourceType) -> tuple[JobStage, ...]:
    return _YOUTUBE_PATH if source_type is SourceType.YOUTUBE else _UPLOAD_PATH


def ensure_transition(
    current: JobStage,
    following: JobStage,
    source_type: SourceType,
) -> None:
    if current in _TERMINAL_STAGES:
        raise ValueError(f"invalid job transition from terminal stage {current}")
    if following is JobStage.FAILED:
        return

    path = success_path(source_type)
    try:
        current_index = path.index(current)
    except ValueError as error:
        raise ValueError(f"invalid job transition from {current}") from error
    if current_index + 1 >= len(path) or path[current_index + 1] is not following:
        raise ValueError(f"invalid job transition from {current} to {following}")


def progress_for_stage(stage: JobStage, fraction: float = 0.0) -> int:
    if stage is JobStage.FAILED:
        raise ValueError("failed progress must retain the last persisted percentage")
    start, end = _PROGRESS_RANGES[stage]
    bounded_fraction = min(1.0, max(0.0, fraction))
    return round(start + ((end - start) * bounded_fraction))


@dataclass(frozen=True)
class RecoveryReport:
    interrupted_jobs: int
    missing_artifacts: int


def recover_on_startup(
    repository: JobRepository,
    *,
    artifact_exists: Callable[[str, ArtifactManifestEntry], bool],
) -> RecoveryReport:
    interrupted_jobs = repository.list_by_stages(_NON_TERMINAL_STAGES)
    for record in interrupted_jobs:
        repository.update(
            record.model_copy(
                update={
                    "stage": JobStage.FAILED,
                    "error": JobError(
                        category=ErrorCategory.INTERRUPTED,
                        stage=record.stage,
                        message="Processing was interrupted by an application restart.",
                    ),
                    "updated_at": datetime.now(UTC),
                }
            )
        )

    completed_jobs = repository.list_by_stages((JobStage.COMPLETED,))
    missing_artifacts = sum(
        not artifact_exists(record.job_id, artifact)
        for record in completed_jobs
        for artifact in record.artifacts
    )
    return RecoveryReport(
        interrupted_jobs=len(interrupted_jobs),
        missing_artifacts=missing_artifacts,
    )
