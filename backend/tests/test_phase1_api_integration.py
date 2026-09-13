from pathlib import Path
from typing import Literal

import pytest
from httpx import ASGITransport, AsyncClient

from subtitle_forge_api.api import JobApiServices
from subtitle_forge_api.app import create_app
from subtitle_forge_api.artifacts import ArtifactPublisher, Phase1Result
from subtitle_forge_api.domain import (
    JobStage,
    SourceType,
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.lifecycle import JobLifecycleService
from subtitle_forge_api.persistence import SQLiteJobRepository
from subtitle_forge_api.pipeline import (
    AcquiredMedia,
    PipelineOrchestrator,
    PipelineRequest,
    PreparedMedia,
)
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.storage import ManagedJobStorage


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class IntegrationFakes:
    def __init__(self, storage: ManagedJobStorage) -> None:
        self.storage = storage
        self.result: Phase1Result | None = None

    def acquire(self, request: PipelineRequest) -> AcquiredMedia:
        if request.source_type is SourceType.YOUTUBE:
            path = self.storage.write_atomic(request.job_id, "source.mp4", b"fixture video")
            return AcquiredMedia(path, SourceType.MP4)
        assert request.source_path is not None
        return AcquiredMedia(request.source_path, request.source_type)

    def prepare(self, job_id: str, media: AcquiredMedia) -> PreparedMedia:
        del job_id
        return PreparedMedia(media.path, 2_000)

    def transcribe(self, audio_path: Path, *, duration_ms: int, progress=None) -> Transcript:  # type: ignore[no-untyped-def]
        del audio_path, duration_ms
        if progress is not None:
            progress(0.5)
        return Transcript(
            segments=(
                TranscriptSegment(
                    segment_id="s1", start_ms=0, end_ms=2_000, source_text="Fixture speech."
                ),
            )
        )

    def translate(self, transcript: Transcript) -> TranslatedTranscript:
        source = transcript.segments[0]
        return TranslatedTranscript(
            segments=(
                TranslatedSegment(
                    segment_id=source.segment_id,
                    start_ms=source.start_ms,
                    end_ms=source.end_ms,
                    translated_text="測試語音。",
                ),
            )
        )

    def summarize(self, transcript: Transcript, language: Literal["en", "zh-TW"]) -> Summary:
        del transcript
        return Summary(
            language=language, text="Fixture summary." if language == "en" else "測試摘要。"
        )

    def publish(self, **values) -> Phase1Result:  # type: ignore[no-untyped-def]
        self.result = ArtifactPublisher(self.storage).publish(**values)
        return self.result

    def cleanup(self, job_id: str, paths: tuple[Path, ...], succeeded: bool) -> None:
        del job_id, paths, succeeded


class CompletingQueue:
    def __init__(self, repository: SQLiteJobRepository, storage: ManagedJobStorage) -> None:
        self.lifecycle = JobLifecycleService(repository)
        self.fakes = IntegrationFakes(storage)
        self.stages: list[JobStage] = []

    async def submit(self, request: PipelineRequest) -> None:
        def report(stage: JobStage, fraction: float) -> None:
            self.stages.append(stage)
            artifacts = (
                self.fakes.result.artifacts
                if stage is JobStage.COMPLETED and self.fakes.result
                else None
            )
            self.lifecycle.report(request.job_id, stage, fraction, artifacts=artifacts)

        PipelineOrchestrator(
            acquirer=self.fakes,
            preparer=self.fakes,
            transcriber=self.fakes,
            translator=self.fakes,
            subtitle_builder=lambda transcript: None,
            summarizer=self.fakes,
            publisher=self.fakes,
            cleanup=self.fakes,
            report_progress=report,
        ).run(request)


@pytest.mark.anyio
@pytest.mark.parametrize("source", ["youtube", "upload"])
async def test_fake_backed_submission_progress_result_and_all_downloads(
    tmp_path: Path, source: str
) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    storage = ManagedJobStorage(tmp_path / "jobs")
    queue = CompletingQueue(repository, storage)
    app = create_app(
        Settings(_env_file=None, data_root=storage.root),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
        job_services=JobApiServices(repository, storage, queue),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if source == "youtube":
            created = await client.post(
                "/api/jobs",
                data={
                    "source_type": "youtube",
                    "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                    "whisper_profile": "balanced",
                },
            )
        else:
            created = await client.post(
                "/api/jobs",
                data={"source_type": "mp3", "whisper_profile": "fast"},
                files={"upload": ("fixture.mp3", b"ID3fixture", "audio/mpeg")},
            )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.json()["stage"] == "COMPLETED"
        manifest = status.json()["result"]["artifacts"]
        assert len(manifest) == 7
        for entry in manifest:
            download = await client.get(f"/api/jobs/{job_id}/artifacts/{entry['artifact_key']}")
            assert download.status_code == 200
            assert download.content
    assert queue.stages[-1] is JobStage.COMPLETED
    assert (JobStage.DOWNLOADING in queue.stages) is (source == "youtube")
    repository.close()
