import importlib.util
from pathlib import Path

import pytest

from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.storage import ManagedJobStorage


def load_intake():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.intake") is not None
    from subtitle_forge_api import intake

    return intake


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=10", "dQw4w9WgXcQ"),
        ("http://m.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_supported_youtube_urls_are_canonicalized(url: str, video_id: str) -> None:
    intake = load_intake()

    parsed = intake.parse_youtube_url(url)

    assert parsed.video_id == video_id
    assert parsed.canonical_url == f"https://www.youtube.com/watch?v={video_id}"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://user:secret@youtube.com/watch?v=dQw4w9WgXcQ",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/article",
        "https://youtube.com/embed/dQw4w9WgXcQ",
        "https://youtube.com/watch?v=short",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
        "https://youtu.be/dQw4w9WgXcQ?list=PL123",
        "https://youtu.be/dQw4w9WgXcQ/extra",
    ],
)
def test_unsupported_or_unsafe_youtube_urls_are_rejected(url: str) -> None:
    intake = load_intake()

    with pytest.raises(ValueError, match="YouTube"):
        intake.parse_youtube_url(url)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class UploadReader:
    def __init__(self, chunks: list[bytes], *, fail_after: int | None = None) -> None:
        self._chunks = chunks
        self._index = 0
        self._fail_after = fail_after

    async def read(self, _size: int) -> bytes:
        if self._fail_after is not None and self._index >= self._fail_after:
            raise OSError("upload interrupted")
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("source_type", "content", "stored_name"),
    [
        (SourceType.MP3, b"ID3" + b"audio" * 10, "source.mp3"),
        (SourceType.MP4, b"\x00\x00\x00\x18ftypmp42" + b"video" * 10, "source.mp4"),
    ],
)
async def test_upload_streams_to_a_generated_managed_name(
    tmp_path: Path,
    source_type: SourceType,
    content: bytes,
    stored_name: str,
) -> None:
    intake = load_intake()
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()

    receipt = await intake.stream_upload(
        storage=storage,
        job_id=job.job_id,
        source_type=source_type,
        original_filename="../hostile name.mp3",
        content_type="application/octet-stream",
        reader=UploadReader([content[:7], content[7:]]),
        max_bytes=1_024,
    )

    assert receipt.path.name == stored_name
    assert receipt.path.read_bytes() == content
    assert receipt.display_name == "hostile name.mp3"
    assert not tuple(job.path.glob("*.tmp"))


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("chunks", "max_bytes"),
    [([], 100), ([b""], 100), ([b"ID3" + b"x" * 20], 10), ([b"not-media"], 100)],
)
async def test_invalid_empty_oversized_or_misleading_upload_is_removed(
    tmp_path: Path,
    chunks: list[bytes],
    max_bytes: int,
) -> None:
    intake = load_intake()
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()

    with pytest.raises(intake.UploadValidationError):
        await intake.stream_upload(
            storage=storage,
            job_id=job.job_id,
            source_type=SourceType.MP3,
            original_filename="claimed.mp3",
            content_type="audio/mpeg",
            reader=UploadReader(chunks),
            max_bytes=max_bytes,
        )

    assert not (job.path / "source.mp3").exists()
    assert not tuple(job.path.glob("*.tmp"))


@pytest.mark.anyio
async def test_interrupted_upload_removes_partial_content(tmp_path: Path) -> None:
    intake = load_intake()
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()

    with pytest.raises(intake.UploadValidationError, match="interrupted"):
        await intake.stream_upload(
            storage=storage,
            job_id=job.job_id,
            source_type=SourceType.MP3,
            original_filename="lesson.mp3",
            content_type="audio/mpeg",
            reader=UploadReader([b"ID3partial"], fail_after=1),
            max_bytes=1_024,
        )

    assert not tuple(job.path.iterdir())


@pytest.mark.parametrize(
    ("youtube_url", "upload_present"),
    [(None, False), ("https://youtu.be/dQw4w9WgXcQ", True)],
)
def test_exactly_one_source_is_required(
    youtube_url: str | None,
    upload_present: bool,
) -> None:
    intake = load_intake()

    with pytest.raises(intake.UploadValidationError, match="exactly one"):
        intake.require_exactly_one_source(youtube_url, upload_present)
