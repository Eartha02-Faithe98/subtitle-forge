"""Contained managed filesystem storage for local jobs and artifacts."""

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4


@dataclass(frozen=True)
class JobDirectory:
    job_id: str
    path: Path


class ManagedJobStorage:
    def __init__(
        self,
        root: Path,
        *,
        atomic_replace: Callable[[Path, Path], None] = os.replace,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_replace = atomic_replace

    def create_job(self) -> JobDirectory:
        while True:
            job_id = str(uuid4())
            path = self.root / job_id
            try:
                path.mkdir()
            except FileExistsError:
                continue
            return JobDirectory(job_id=job_id, path=path)

    def resolve_member(self, job_id: str, filename: str) -> Path:
        job_path = self._job_path(job_id)
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or Path(filename).is_absolute()
        ):
            raise ValueError("member must be a plain filename inside managed storage")
        member = (job_path / filename).resolve()
        self._ensure_within_root(member)
        if member.parent != job_path:
            raise ValueError("member must stay inside its managed job directory")
        return member

    def write_atomic(self, job_id: str, filename: str, content: bytes) -> Path:
        destination = self.resolve_member(job_id, filename)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        self._ensure_within_root(temporary)
        try:
            temporary.write_bytes(content)
            self._atomic_replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def publish_temporary(
        self,
        job_id: str,
        temporary_filename: str,
        destination_filename: str,
    ) -> Path:
        temporary = self.resolve_member(job_id, temporary_filename)
        destination = self.resolve_member(job_id, destination_filename)
        self._atomic_replace(temporary, destination)
        return destination

    def cleanup_disposable(self, job_id: str, filenames: Iterable[str]) -> None:
        for filename in filenames:
            self.resolve_member(job_id, filename).unlink(missing_ok=True)

    def _job_path(self, job_id: str) -> Path:
        try:
            parsed = UUID(job_id)
        except ValueError as error:
            raise ValueError("job identifier must resolve inside managed storage") from error
        if str(parsed) != job_id:
            raise ValueError("job identifier must use canonical UUID form")
        path = (self.root / job_id).resolve()
        self._ensure_within_root(path)
        if path.parent != self.root:
            raise ValueError("job path must stay inside managed storage")
        return path

    def _ensure_within_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ValueError("path must stay inside managed storage") from error
