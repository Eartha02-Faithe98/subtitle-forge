from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from subtitle_forge_api.api import JobApiServices
from subtitle_forge_api.app import create_app
from subtitle_forge_api.domain import JobStage
from subtitle_forge_api.persistence import SQLiteJobRepository
from subtitle_forge_api.pipeline import PipelineRequest
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.storage import ManagedJobStorage


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class CapturingQueue:
    def __init__(self) -> None:
        self.requests: list[PipelineRequest] = []

    async def submit(self, request: PipelineRequest) -> None:
        self.requests.append(request)


def api(tmp_path: Path, *, upload_limit: int = 1_024):
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.initialize()
    storage = ManagedJobStorage(tmp_path / "jobs")
    queue = CapturingQueue()
    app = create_app(
        Settings(_env_file=None, data_root=storage.root, upload_max_bytes=upload_limit),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
        job_services=JobApiServices(repository=repository, storage=storage, queue=queue),
    )
    return app, repository, storage, queue


@pytest.mark.anyio
async def test_youtube_job_is_created_with_http_202_and_canonical_source(tmp_path: Path) -> None:
    app, repository, _storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            data={
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "balanced",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["api_version"] == "1"
    assert payload["status_url"] == f"/api/jobs/{payload['job_id']}"
    record = repository.get(payload["job_id"])
    assert record is not None
    assert record.source_metadata == {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "whisper_profile": "balanced",
    }
    assert queue.requests[0].youtube_url == record.source_metadata["youtube_url"]
    assert queue.requests[0].whisper_profile.value == "balanced"
    repository.close()


@pytest.mark.anyio
async def test_youtube_job_accepts_configured_browser_origin(tmp_path: Path) -> None:
    app, repository, _storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            headers={"Origin": "http://localhost:3000"},
            data={
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "balanced",
            },
        )

    assert response.status_code == 202
    assert len(queue.requests) == 1
    repository.close()


@pytest.mark.anyio
@pytest.mark.parametrize("origin", ["https://untrusted.example", "not an origin"])
async def test_job_creation_rejects_untrusted_origin_before_side_effects(
    tmp_path: Path, origin: str
) -> None:
    app, repository, storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            headers={"Origin": origin},
            data={
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "balanced",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "This browser origin is not allowed."}
    assert queue.requests == []
    assert repository.list_by_stages(tuple(JobStage)) == ()
    assert list(storage.root.iterdir()) == []
    repository.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("source_type", "filename", "content", "stored_name"),
    [
        ("mp3", "../hostile.mp3", b"ID3audio", "source.mp3"),
        ("mp4", "video.exe", b"\x00\x00\x00\x18ftypmp42video", "source.mp4"),
    ],
)
async def test_upload_job_streams_to_managed_path_and_returns_202(
    tmp_path: Path,
    source_type: str,
    filename: str,
    content: bytes,
    stored_name: str,
) -> None:
    app, repository, storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            data={"source_type": source_type, "whisper_profile": "fast"},
            files={"upload": (filename, content, "application/octet-stream")},
        )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert storage.resolve_member(job_id, stored_name).read_bytes() == content
    assert queue.requests[0].source_path == storage.resolve_member(job_id, stored_name)
    assert queue.requests[0].whisper_profile.value == "fast"
    assert repository.get(job_id).source_metadata["display_name"] == filename.rsplit("/", 1)[-1]  # type: ignore[union-attr]
    repository.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("data", "files", "message"),
    [
        ({"source_type": "youtube", "whisper_profile": "fast"}, None, "exactly one"),
        (
            {
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "fast",
            },
            {"upload": ("audio.mp3", b"ID3audio", "audio/mpeg")},
            "exactly one",
        ),
        (
            {"source_type": "mp3", "whisper_profile": "fast"},
            {"upload": ("empty.mp3", b"", "audio/mpeg")},
            "empty",
        ),
        (
            {"source_type": "mp3", "whisper_profile": "fast"},
            {"upload": ("fake.mp3", b"not media", "audio/mpeg")},
            "not a valid MP3",
        ),
    ],
)
async def test_media_intake_validation_errors_are_safe(
    tmp_path: Path,
    data: dict[str, str],
    files: object,
    message: str,
) -> None:
    app, repository, _storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/jobs", data=data, files=files)

    assert response.status_code == 422
    assert message.lower() in response.json()["detail"].lower()
    assert queue.requests == []
    repository.close()


@pytest.mark.anyio
async def test_oversized_upload_is_rejected_without_partial_source(tmp_path: Path) -> None:
    app, repository, storage, queue = api(tmp_path, upload_limit=5)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            data={"source_type": "mp3", "whisper_profile": "fast"},
            files={"upload": ("large.mp3", b"ID3large", "audio/mpeg")},
        )

    assert response.status_code == 422
    assert "size limit" in response.json()["detail"]
    assert queue.requests == []
    assert not list(storage.root.rglob("source.mp3"))
    repository.close()
