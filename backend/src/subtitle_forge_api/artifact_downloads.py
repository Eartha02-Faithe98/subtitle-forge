"""Server-controlled artifact-key lookup and bounded download streaming."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from subtitle_forge_api.artifacts import Phase1Result
from subtitle_forge_api.storage import ManagedJobStorage


class ArtifactLookupError(ValueError):
    """A requested artifact cannot be safely served."""


@dataclass(frozen=True, repr=False)
class ArtifactDownload:
    filename: str
    media_type: str
    size_bytes: int
    _path: Path

    def __repr__(self) -> str:
        return (
            "ArtifactDownload("
            f"filename={self.filename!r}, media_type={self.media_type!r}, "
            f"size_bytes={self.size_bytes!r})"
        )

    def public_metadata(self) -> dict[str, str | int]:
        return {
            "filename": self.filename,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
        }

    def iter_bytes(self, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        try:
            with self._path.open("rb") as source:
                while chunk := source.read(chunk_size):
                    yield chunk
        except OSError as error:
            raise ArtifactLookupError("Artifact is not available for download") from error


class ArtifactDownloadService:
    def __init__(self, storage: ManagedJobStorage) -> None:
        self._storage = storage

    def resolve(
        self,
        job_id: str,
        artifact_key: str,
        *,
        requested_range: str | None = None,
    ) -> ArtifactDownload:
        if requested_range is not None:
            raise ArtifactLookupError("Artifact range requests are not supported")
        if (
            not artifact_key
            or "/" in artifact_key
            or "\\" in artifact_key
            or artifact_key in {".", ".."}
        ):
            raise ArtifactLookupError("Artifact is not available for download")
        try:
            result_path = self._storage.resolve_member(job_id, "result.json")
            result = Phase1Result.model_validate_json(result_path.read_bytes())
            if result.job_id != job_id:
                raise ArtifactLookupError("Artifact is not available for download")
            entry = next(
                (
                    candidate
                    for candidate in result.artifacts
                    if candidate.artifact_key == artifact_key
                ),
                None,
            )
            if entry is None:
                raise ArtifactLookupError("Artifact is not available for download")
            path = self._storage.resolve_member(job_id, entry.filename)
            if not path.is_file() or path.stat().st_size != entry.size_bytes:
                raise ArtifactLookupError("Artifact is not available for download")
            return ArtifactDownload(
                filename=f"subtitle-forge-{job_id[:8]}-{entry.filename}",
                media_type=entry.media_type,
                size_bytes=entry.size_bytes,
                _path=path,
            )
        except ArtifactLookupError:
            raise
        except Exception as error:
            raise ArtifactLookupError("Artifact is not available for download") from error
