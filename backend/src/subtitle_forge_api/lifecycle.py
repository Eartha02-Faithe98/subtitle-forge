"""Persisted monotonic job lifecycle and polling-stage derivation."""

from collections.abc import Callable
from datetime import UTC, datetime

from subtitle_forge_api.domain import ArtifactKind, ArtifactManifestEntry, JobStage
from subtitle_forge_api.jobs import ensure_transition, progress_for_stage, success_path
from subtitle_forge_api.persistence import JobNotFoundError, JobRecord, JobRepository

CompletionGuard = Callable[[JobRecord], None]


class JobLifecycleService:
    def __init__(
        self,
        repository: JobRepository,
        *,
        completion_guard: CompletionGuard | None = None,
    ) -> None:
        self._repository = repository
        self._completion_guard = completion_guard or _require_seven_artifacts

    def report(
        self,
        job_id: str,
        stage: JobStage,
        fraction: float = 0.0,
        *,
        artifacts: tuple[ArtifactManifestEntry, ...] | None = None,
    ) -> JobRecord:
        record = self._repository.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        if stage is JobStage.FAILED:
            raise ValueError("failed jobs must use the safe failure service")

        if stage is not record.stage:
            ensure_transition(record.stage, stage, record.source_type)
        elif stage in {JobStage.COMPLETED, JobStage.FAILED}:
            return record

        next_progress = max(record.progress, progress_for_stage(stage, fraction))
        next_artifacts = record.artifacts if artifacts is None else artifacts
        candidate = record.model_copy(
            update={
                "stage": stage,
                "progress": next_progress,
                "artifacts": next_artifacts,
                "updated_at": datetime.now(UTC),
            }
        )
        if stage is JobStage.COMPLETED:
            self._completion_guard(candidate)
        elif artifacts is not None:
            raise ValueError("artifacts can be published only with completion")
        self._repository.update(candidate)
        return candidate


def completed_stages(record: JobRecord) -> tuple[JobStage, ...]:
    path = success_path(record.source_type)
    if record.stage is JobStage.FAILED:
        active_stage = record.error.stage if record.error is not None else None
        if active_stage not in path:
            return ()
    else:
        active_stage = record.stage
    try:
        active_index = path.index(active_stage)
    except ValueError:
        return ()
    return tuple(stage for stage in path[1:active_index] if stage is not JobStage.COMPLETED)


def _require_seven_artifacts(record: JobRecord) -> None:
    if len(record.artifacts) != len(ArtifactKind) or {
        artifact.kind for artifact in record.artifacts
    } != set(ArtifactKind):
        raise ValueError("completed job requires a valid seven-artifact manifest")
