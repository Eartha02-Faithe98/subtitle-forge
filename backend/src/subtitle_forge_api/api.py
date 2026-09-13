"""Versioned FastAPI job submission boundary for Phase 1."""

from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from subtitle_forge_api.artifact_downloads import (
    ArtifactDownloadService,
    ArtifactLookupError,
)
from subtitle_forge_api.artifacts import Phase1Result
from subtitle_forge_api.domain import JobError, JobStage, SourceType, WhisperProfile
from subtitle_forge_api.intake import (
    UploadValidationError,
    parse_youtube_url,
    require_exactly_one_source,
    stream_upload,
)
from subtitle_forge_api.lifecycle import completed_stages
from subtitle_forge_api.persistence import JobRecord, JobRepository
from subtitle_forge_api.pipeline import PipelineRequest
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.storage import ManagedJobStorage


class JobQueue(Protocol):
    async def submit(self, request: PipelineRequest) -> None: ...


@dataclass(frozen=True)
class JobApiServices:
    repository: JobRepository
    storage: ManagedJobStorage
    queue: JobQueue


class JobCreatedResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_version: str = "1"
    job_id: str
    status_url: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_version: str = "1"
    job_id: str
    stage: JobStage
    stage_label: str
    progress: int
    completed_stages: tuple[JobStage, ...]
    error: JobError | None = None
    result: Phase1Result | None = None


_STAGE_LABELS = {
    JobStage.PENDING: "Waiting to start",
    JobStage.DOWNLOADING: "Downloading YouTube media",
    JobStage.EXTRACTING_AUDIO: "Preparing audio",
    JobStage.TRANSCRIBING: "Transcribing with Local Whisper",
    JobStage.TRANSLATING: "Translating to Traditional Chinese",
    JobStage.GENERATING_SUBTITLES: "Generating subtitles",
    JobStage.GENERATING_SUMMARY: "Generating summaries",
    JobStage.COMPLETED: "Completed",
    JobStage.FAILED: "Failed",
}


def register_job_routes(
    application: FastAPI,
    *,
    services: JobApiServices,
    settings: Settings,
) -> None:
    @application.post(
        "/api/jobs",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=JobCreatedResponse,
    )
    async def create_job(
        source_type: Annotated[SourceType, Form()],
        whisper_profile: Annotated[WhisperProfile, Form()],
        youtube_url: Annotated[str | None, Form()] = None,
        upload: Annotated[UploadFile | None, File()] = None,
    ) -> JobCreatedResponse:
        try:
            require_exactly_one_source(youtube_url, upload is not None)
            _validate_source_fields(source_type, youtube_url, upload)
            parsed_youtube = (
                parse_youtube_url(youtube_url)
                if source_type is SourceType.YOUTUBE and youtube_url is not None
                else None
            )
            job = services.storage.create_job()
            if upload is not None:
                try:
                    receipt = await stream_upload(
                        storage=services.storage,
                        job_id=job.job_id,
                        source_type=source_type,
                        original_filename=upload.filename or f"upload.{source_type.value}",
                        content_type=upload.content_type or "application/octet-stream",
                        reader=upload,
                        max_bytes=settings.upload_max_bytes,
                    )
                finally:
                    await upload.close()
                source_path = receipt.path
                source_metadata = {
                    "display_name": receipt.display_name,
                    "whisper_profile": whisper_profile.value,
                }
                request = PipelineRequest(
                    job_id=job.job_id,
                    source_type=source_type,
                    whisper_profile=whisper_profile,
                    source_path=source_path,
                )
            else:
                assert parsed_youtube is not None
                source_metadata = {
                    "youtube_url": parsed_youtube.canonical_url,
                    "whisper_profile": whisper_profile.value,
                }
                request = PipelineRequest(
                    job_id=job.job_id,
                    source_type=source_type,
                    whisper_profile=whisper_profile,
                    youtube_url=parsed_youtube.canonical_url,
                )
        except (UploadValidationError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error

        services.repository.create(
            JobRecord(
                job_id=job.job_id,
                source_type=source_type,
                source_metadata=source_metadata,
            )
        )
        try:
            await services.queue.submit(request)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The local processing worker is unavailable.",
            ) from error
        return JobCreatedResponse(
            job_id=job.job_id,
            status_url=f"/api/jobs/{job.job_id}",
        )

    @application.get(
        "/api/jobs/{job_id}",
        response_model=JobStatusResponse,
    )
    def get_job(job_id: str) -> JobStatusResponse:
        record = services.repository.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job was not found.",
            )
        result: Phase1Result | None = None
        if record.stage is JobStage.COMPLETED:
            try:
                result_path = services.storage.resolve_member(job_id, "result.json")
                result = Phase1Result.model_validate_json(result_path.read_bytes())
                if result.job_id != job_id:
                    raise ValueError("result belongs to another job")
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Job result is unavailable.",
                ) from error
        return JobStatusResponse(
            job_id=record.job_id,
            stage=record.stage,
            stage_label=_STAGE_LABELS[record.stage],
            progress=record.progress,
            completed_stages=completed_stages(record),
            error=record.error,
            result=result,
        )

    @application.get("/api/jobs/{job_id}/artifacts/{artifact_key}")
    def download_artifact(
        job_id: str,
        artifact_key: str,
        requested_range: Annotated[str | None, Header(alias="Range")] = None,
    ) -> StreamingResponse:
        try:
            download = ArtifactDownloadService(services.storage).resolve(
                job_id,
                artifact_key,
                requested_range=requested_range,
            )
        except ArtifactLookupError as error:
            if requested_range is not None:
                raise HTTPException(
                    status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                    detail="Artifact range requests are not supported.",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact is not available for download.",
            ) from error
        return StreamingResponse(
            download.iter_bytes(),
            media_type=download.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{download.filename}"',
                "Content-Length": str(download.size_bytes),
                "X-Content-Type-Options": "nosniff",
            },
        )


def _validate_source_fields(
    source_type: SourceType,
    youtube_url: str | None,
    upload: UploadFile | None,
) -> None:
    if source_type is SourceType.YOUTUBE and upload is not None:
        raise UploadValidationError("YouTube source type requires a YouTube URL")
    if source_type is not SourceType.YOUTUBE and youtube_url and youtube_url.strip():
        raise UploadValidationError("MP3 or MP4 source type requires one file upload")
