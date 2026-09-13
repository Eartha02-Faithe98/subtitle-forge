from pathlib import Path

import pytest

from subtitle_forge_api.artifact_downloads import ArtifactDownloadService, ArtifactLookupError
from subtitle_forge_api.artifacts import ArtifactPublisher
from subtitle_forge_api.domain import (
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.storage import ManagedJobStorage


def published_storage(tmp_path: Path) -> tuple[ManagedJobStorage, str]:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    transcript = Transcript(
        segments=(
            TranscriptSegment(
                segment_id="s1", start_ms=0, end_ms=1_000, source_text="Hello download."
            ),
        )
    )
    translated = TranslatedTranscript(
        segments=(
            TranslatedSegment(
                segment_id="s1", start_ms=0, end_ms=1_000, translated_text="哈囉，下載。"
            ),
        )
    )
    ArtifactPublisher(storage).publish(
        job_id=job.job_id,
        transcript=transcript,
        translated=translated,
        english_summary=Summary(language="en", text="Download summary."),
        chinese_summary=Summary(language="zh-TW", text="下載摘要。"),
    )
    return storage, job.job_id


def test_resolves_key_to_safe_streaming_metadata_and_bounded_bytes(tmp_path: Path) -> None:
    storage, job_id = published_storage(tmp_path)
    download = ArtifactDownloadService(storage).resolve(job_id, "traditional_chinese_transcript")

    assert download.filename.startswith("subtitle-forge-")
    assert download.filename.endswith("-transcript-zh-TW.txt")
    assert download.media_type == "text/plain; charset=utf-8"
    content = b"".join(download.iter_bytes(chunk_size=4))
    assert content.decode("utf-8") == "[00:00:00] 哈囉，下載。\n"
    assert download.size_bytes == len(content)
    public = download.public_metadata()
    assert public == {
        "filename": download.filename,
        "media_type": download.media_type,
        "size_bytes": download.size_bytes,
    }
    assert str(storage.root) not in repr(download)
    assert str(storage.root) not in str(public)


@pytest.mark.parametrize(
    "artifact_key", ["unknown", "../english_transcript", "english_transcript/../../source.mp4", ""]
)
def test_unknown_and_path_injection_keys_are_rejected(tmp_path: Path, artifact_key: str) -> None:
    storage, job_id = published_storage(tmp_path)
    with pytest.raises(ArtifactLookupError, match="not available"):
        ArtifactDownloadService(storage).resolve(job_id, artifact_key)


def test_unknown_job_and_missing_artifact_are_safe(tmp_path: Path) -> None:
    storage, job_id = published_storage(tmp_path)
    service = ArtifactDownloadService(storage)
    with pytest.raises(ArtifactLookupError, match="not available"):
        service.resolve("00000000-0000-0000-0000-000000000000", "english_srt")
    storage.resolve_member(job_id, "subtitles-en.srt").unlink()
    with pytest.raises(ArtifactLookupError, match="not available"):
        service.resolve(job_id, "english_srt")


def test_cross_job_lookup_never_uses_another_job_directory(tmp_path: Path) -> None:
    storage, first_job_id = published_storage(tmp_path)
    second_job = storage.create_job()
    storage.write_atomic(second_job.job_id, "transcript-en.txt", b"other job secret")
    first = ArtifactDownloadService(storage).resolve(first_job_id, "english_transcript")
    assert b"other job secret" not in b"".join(first.iter_bytes())


@pytest.mark.parametrize("requested_range", ["bytes=0-10", "../../source.mp4", "bytes=0-1\r\nX: y"])
def test_untrusted_range_requests_are_not_interpreted(tmp_path: Path, requested_range: str) -> None:
    storage, job_id = published_storage(tmp_path)
    with pytest.raises(ArtifactLookupError, match="range"):
        ArtifactDownloadService(storage).resolve(
            job_id, "english_transcript", requested_range=requested_range
        )
