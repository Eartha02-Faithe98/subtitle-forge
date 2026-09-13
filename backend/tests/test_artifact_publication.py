from pathlib import Path

import pytest
from pydantic import ValidationError

from subtitle_forge_api.artifacts import (
    ArtifactPublicationError,
    ArtifactPublisher,
    Phase1Result,
    assert_ready_for_completion,
)
from subtitle_forge_api.domain import (
    ArtifactKind,
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.storage import ManagedJobStorage


def canonical_data() -> tuple[Transcript, TranslatedTranscript, Summary, Summary]:
    transcript = Transcript(
        segments=(
            TranscriptSegment(
                segment_id="s1",
                start_ms=0,
                end_ms=1_000,
                source_text="Hello world.",
            ),
        )
    )
    translated = TranslatedTranscript(
        segments=(
            TranslatedSegment(
                segment_id="s1",
                start_ms=0,
                end_ms=1_000,
                translated_text="哈囉，世界。",
            ),
        )
    )
    return (
        transcript,
        translated,
        Summary(language="en", text="English summary."),
        Summary(language="zh-TW", text="繁體中文摘要。"),
    )


def publish(tmp_path: Path) -> tuple[ManagedJobStorage, str, Phase1Result]:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    transcript, translated, english_summary, chinese_summary = canonical_data()
    result = ArtifactPublisher(storage).publish(
        job_id=job.job_id,
        transcript=transcript,
        translated=translated,
        english_summary=english_summary,
        chinese_summary=chinese_summary,
    )
    return storage, job.job_id, result


def test_publishes_exactly_seven_atomic_artifacts_then_versioned_result(
    tmp_path: Path,
) -> None:
    storage, job_id, result = publish(tmp_path)

    assert result.schema_version == "1.0"
    assert result.job_id == job_id
    assert len(result.artifacts) == 7
    assert {entry.kind for entry in result.artifacts} == set(ArtifactKind)
    assert len({entry.artifact_key for entry in result.artifacts}) == 7
    assert len({entry.filename for entry in result.artifacts}) == 7
    for entry in result.artifacts:
        path = storage.resolve_member(job_id, entry.filename)
        assert path.is_file()
        assert path.stat().st_size == entry.size_bytes > 0
    result_path = storage.resolve_member(job_id, "result.json")
    assert Phase1Result.model_validate_json(result_path.read_bytes()) == result
    assert not list(result_path.parent.glob("*.tmp"))
    assert_ready_for_completion(storage, result)


class FailingStorage(ManagedJobStorage):
    def __init__(self, root: Path, fail_on_write: int) -> None:
        super().__init__(root)
        self.fail_on_write = fail_on_write
        self.write_count = 0

    def write_atomic(self, job_id: str, filename: str, content: bytes) -> Path:
        self.write_count += 1
        if self.write_count == self.fail_on_write:
            raise OSError("simulated partial publication")
        return super().write_atomic(job_id, filename, content)


def test_partial_publication_is_rolled_back_without_result_manifest(
    tmp_path: Path,
) -> None:
    storage = FailingStorage(tmp_path / "jobs", fail_on_write=3)
    job = storage.create_job()
    transcript, translated, english_summary, chinese_summary = canonical_data()

    with pytest.raises(ArtifactPublicationError, match="publish"):
        ArtifactPublisher(storage).publish(
            job_id=job.job_id,
            transcript=transcript,
            translated=translated,
            english_summary=english_summary,
            chinese_summary=chinese_summary,
        )

    assert list(job.path.iterdir()) == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate_kind", "duplicate_file"])
def test_result_model_rejects_missing_or_duplicate_artifacts(
    tmp_path: Path,
    mutation: str,
) -> None:
    _storage, _job_id, result = publish(tmp_path)
    entries = list(result.artifacts)
    if mutation == "missing":
        entries.pop()
    elif mutation == "duplicate_kind":
        entries[-1] = entries[0].model_copy(update={"artifact_key": "other"})
    else:
        entries[-1] = entries[-1].model_copy(update={"filename": entries[0].filename})

    with pytest.raises(ValidationError):
        Phase1Result(
            job_id=result.job_id,
            transcript=result.transcript,
            translated=result.translated,
            summaries=result.summaries,
            artifacts=tuple(entries),
        )


@pytest.mark.parametrize("damage", ["missing", "partial", "invalid_result"])
def test_completion_guard_rejects_missing_partial_or_invalid_files(
    tmp_path: Path,
    damage: str,
) -> None:
    storage, _job_id, result = publish(tmp_path)
    if damage == "missing":
        storage.resolve_member(result.job_id, result.artifacts[0].filename).unlink()
    elif damage == "partial":
        storage.resolve_member(result.job_id, result.artifacts[0].filename).write_bytes(b"x")
    else:
        storage.resolve_member(result.job_id, "result.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ArtifactPublicationError, match="complete"):
        assert_ready_for_completion(storage, result)
