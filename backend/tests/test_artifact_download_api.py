from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from subtitle_forge_api.api import JobApiServices
from subtitle_forge_api.app import create_app
from subtitle_forge_api.artifacts import ArtifactPublisher
from subtitle_forge_api.domain import (
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
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


def completed_app(tmp_path: Path):  # type: ignore[no-untyped-def]
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    transcript = Transcript(
        segments=(
            TranscriptSegment(
                segment_id="s1", start_ms=0, end_ms=1_000, source_text="Download me."
            ),
        )
    )
    translated = TranslatedTranscript(
        segments=(
            TranslatedSegment(
                segment_id="s1", start_ms=0, end_ms=1_000, translated_text="下載我。"
            ),
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
            source_type="mp3",
            stage="COMPLETED",
            progress=100,
            artifacts=result.artifacts,
        )
    )
    app = create_app(
        Settings(_env_file=None, data_root=storage.root),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
        job_services=JobApiServices(repository, storage, NoopQueue()),
    )
    return app, repository, storage, job.job_id


@pytest.mark.anyio
async def test_download_streams_server_controlled_artifact_with_safe_headers(
    tmp_path: Path,
) -> None:
    app, repository, _storage, job_id = completed_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job_id}/artifacts/english_srt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-subrip")
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="subtitle-forge-'
    )
    assert response.text.startswith("1\n00:00:00,000 --> 00:00:01,000")
    assert int(response.headers["content-length"]) == len(response.content)
    repository.close()


@pytest.mark.anyio
@pytest.mark.parametrize("suffix", ["unknown", "%2e%2e"])
async def test_unknown_and_traversal_artifact_keys_return_safe_404(
    tmp_path: Path, suffix: str
) -> None:
    app, repository, storage, job_id = completed_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job_id}/artifacts/{suffix}")
    assert response.status_code == 404
    assert str(storage.root) not in response.text
    repository.close()


@pytest.mark.anyio
async def test_unknown_job_missing_file_and_range_are_rejected(tmp_path: Path) -> None:
    app, repository, storage, job_id = completed_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unknown = await client.get(
            "/api/jobs/00000000-0000-0000-0000-000000000000/artifacts/english_srt"
        )
        ranged = await client.get(
            f"/api/jobs/{job_id}/artifacts/english_srt", headers={"Range": "bytes=0-10"}
        )
        storage.resolve_member(job_id, "subtitles-en.srt").unlink()
        missing = await client.get(f"/api/jobs/{job_id}/artifacts/english_srt")
    assert unknown.status_code == 404
    assert ranged.status_code == 416
    assert missing.status_code == 404
    repository.close()
