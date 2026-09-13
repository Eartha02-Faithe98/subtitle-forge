import importlib.util
from pathlib import Path
from uuid import UUID

import pytest


def load_storage():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.storage") is not None
    from subtitle_forge_api import storage

    return storage


def test_job_directories_use_generated_identifiers_inside_managed_root(tmp_path: Path) -> None:
    storage = load_storage()
    managed = storage.ManagedJobStorage(tmp_path / "jobs")

    first = managed.create_job()
    second = managed.create_job()

    UUID(first.job_id)
    assert first.job_id != second.job_id
    assert first.path.parent == (tmp_path / "jobs").resolve()
    assert first.path.is_dir()


@pytest.mark.parametrize(
    "filename",
    ["../outside.txt", "subdir/file.txt", "subdir\\file.txt", "C:/outside.txt", ".."],
)
def test_managed_members_reject_hostile_paths(tmp_path: Path, filename: str) -> None:
    storage = load_storage()
    managed = storage.ManagedJobStorage(tmp_path / "jobs")
    job = managed.create_job()

    with pytest.raises(ValueError, match="managed"):
        managed.resolve_member(job.job_id, filename)


def test_atomic_write_publishes_complete_content(tmp_path: Path) -> None:
    storage = load_storage()
    managed = storage.ManagedJobStorage(tmp_path / "jobs")
    job = managed.create_job()

    destination = managed.write_atomic(job.job_id, "result.json", b'{"version":1}')

    assert destination.read_bytes() == b'{"version":1}'
    assert not tuple(job.path.glob("*.tmp"))


def test_failed_atomic_replace_removes_partial_file(tmp_path: Path) -> None:
    storage = load_storage()

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    managed = storage.ManagedJobStorage(tmp_path / "jobs", atomic_replace=fail_replace)
    job = managed.create_job()

    with pytest.raises(OSError, match="replace failed"):
        managed.write_atomic(job.job_id, "result.json", b"partial")

    assert not (job.path / "result.json").exists()
    assert not tuple(job.path.glob("*.tmp"))


def test_terminal_cleanup_removes_only_declared_disposable_members(tmp_path: Path) -> None:
    storage = load_storage()
    managed = storage.ManagedJobStorage(tmp_path / "jobs")
    job = managed.create_job()
    source = managed.write_atomic(job.job_id, "source.mp4", b"source")
    audio = managed.write_atomic(job.job_id, "audio.wav", b"audio")
    result = managed.write_atomic(job.job_id, "result.json", b"result")

    managed.cleanup_disposable(job.job_id, ("source.mp4", "audio.wav"))

    assert not source.exists()
    assert not audio.exists()
    assert result.exists()


def test_cleanup_refuses_out_of_root_job_identifier(tmp_path: Path) -> None:
    storage = load_storage()
    managed = storage.ManagedJobStorage(tmp_path / "jobs")

    with pytest.raises(ValueError, match="managed"):
        managed.cleanup_disposable("../outside", ("file.txt",))
