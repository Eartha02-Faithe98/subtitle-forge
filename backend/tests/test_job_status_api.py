from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from subtitle_forge_api.api import JobApiServices
from subtitle_forge_api.app import create_app
from subtitle_forge_api.artifacts import ArtifactPublisher
from subtitle_forge_api.domain import (
    JobStage,
    SourceType,
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.errors import SafeJobFailureService
from subtitle_forge_api.persistence import JobRecord, SQLiteJobRepository
from subtitle_forge_api.pipeline import PipelineRequest
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.storage import ManagedJobStorage


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class NoopQueue:
    async def submit(self, request: PipelineRequest) -> None:
        del request


def services(tmp_path: Path) -> tuple[object, SQLiteJobRepository, ManagedJobStorage]:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    storage = ManagedJobStorage(tmp_path / "jobs")
    app = create_app(
        Settings(_env_file=None, data_root=storage.root),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
        job_services=JobApiServices(repository, storage, NoopQueue()),
    )
    return app, repository, storage


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stage",
    [
        JobStage.PENDING,
        JobStage.DOWNLOADING,
        JobStage.EXTRACTING_AUDIO,
        JobStage.TRANSCRIBING,
        JobStage.TRANSLATING,
        JobStage.GENERATING_SUBTITLES,
        JobStage.GENERATING_SUMMARY,
    ],
)
async def test_status_returns_every_active_stage_without_internal_metadata(
    tmp_path: Path, stage: JobStage
) -> None:
    app, repository, storage = services(tmp_path)
    job = storage.create_job()
    repository.create(
        JobRecord(
            job_id=job.job_id,
            source_type=SourceType.YOUTUBE,
            stage=stage,
            progress=25,
            source_metadata={"internal_path": "C:\\private", "token": "secret"},
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job.job_id}")
    payload = response.json()
    assert response.status_code == 200
    assert payload["api_version"] == "1"
    assert payload["stage"] == stage.value
    assert payload["stage_label"]
    assert payload["progress"] == 25
    assert payload["result"] is None
    assert "source_metadata" not in payload
    assert "private" not in response.text.lower()
    assert "secret" not in response.text.lower()
    repository.close()


@pytest.mark.anyio
async def test_failed_status_exposes_only_safe_category_stage_and_message(tmp_path: Path) -> None:
    app, repository, storage = services(tmp_path)
    job = storage.create_job()
    repository.create(
        JobRecord(
            job_id=job.job_id, source_type=SourceType.MP4, stage=JobStage.TRANSCRIBING, progress=42
        )
    )
    SafeJobFailureService(repository).fail(
        job.job_id, RuntimeError("stack trace token=secret prompt C:\\private\\audio.wav")
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job.job_id}")
    payload = response.json()
    assert response.status_code == 200
    assert payload["stage"] == "FAILED"
    assert payload["progress"] == 42
    assert payload["error"] == {
        "category": "unexpected",
        "stage": "TRANSCRIBING",
        "message": "Processing stopped because of an unexpected local error.",
    }
    for secret in ("stack trace", "token", "prompt", "private", "audio.wav"):
        assert secret not in response.text.lower()
    repository.close()


@pytest.mark.anyio
async def test_completed_status_includes_canonical_result_and_download_manifest(
    tmp_path: Path,
) -> None:
    app, repository, storage = services(tmp_path)
    job = storage.create_job()
    transcript = Transcript(
        segments=(
            TranscriptSegment(segment_id="s1", start_ms=0, end_ms=1_000, source_text="Hello."),
        )
    )
    translated = TranslatedTranscript(
        segments=(
            TranslatedSegment(segment_id="s1", start_ms=0, end_ms=1_000, translated_text="哈囉。"),
        )
    )
    result = ArtifactPublisher(storage).publish(
        job_id=job.job_id,
        transcript=transcript,
        translated=translated,
        english_summary=Summary(language="en", text="Summary."),
        chinese_summary=Summary(language="zh-TW", text="摘要。"),
    )
    repository.create(
        JobRecord(
            job_id=job.job_id,
            source_type=SourceType.MP3,
            stage=JobStage.COMPLETED,
            progress=100,
            artifacts=result.artifacts,
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job.job_id}")
    payload = response.json()
    assert response.status_code == 200
    assert payload["progress"] == 100
    assert payload["result"]["schema_version"] == "1.0"
    assert len(payload["result"]["artifacts"]) == 7
    assert payload["completed_stages"] == [
        "EXTRACTING_AUDIO",
        "TRANSCRIBING",
        "TRANSLATING",
        "GENERATING_SUBTITLES",
        "GENERATING_SUMMARY",
    ]
    assert str(storage.root) not in response.text
    repository.close()


@pytest.mark.anyio
async def test_unknown_job_returns_safe_404(tmp_path: Path) -> None:
    app, repository, _storage = services(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json() == {"detail": "Job was not found."}
    repository.close()
