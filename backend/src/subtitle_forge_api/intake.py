"""Validation for the narrowly supported Phase 1 media sources."""

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.storage import ManagedJobStorage

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_SHORT_HOST = "youtu.be"
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


@dataclass(frozen=True)
class YouTubeSource:
    video_id: str
    canonical_url: str


class UploadReader(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class UploadValidationError(ValueError):
    """Safe validation error suitable for returning to the local UI."""


@dataclass(frozen=True)
class UploadReceipt:
    path: Path
    display_name: str
    size_bytes: int


def require_exactly_one_source(
    youtube_url: str | None,
    upload_present: bool,
) -> None:
    has_youtube_url = bool(youtube_url and youtube_url.strip())
    if has_youtube_url == upload_present:
        raise UploadValidationError(
            "Provide exactly one source: a YouTube URL or one MP3/MP4 upload"
        )


async def stream_upload(
    *,
    storage: ManagedJobStorage,
    job_id: str,
    source_type: SourceType,
    original_filename: str,
    content_type: str,
    reader: UploadReader,
    max_bytes: int,
) -> UploadReceipt:
    """Stream an upload to a generated contained path and validate its signature."""
    del content_type  # Client-provided MIME types are deliberately not trusted.
    if source_type not in {SourceType.MP3, SourceType.MP4}:
        raise UploadValidationError("Only MP3 and MP4 uploads are supported")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    destination_filename = f"source.{source_type.value}"
    temporary_filename = f".{destination_filename}.{uuid4().hex}.tmp"
    temporary = storage.resolve_member(job_id, temporary_filename)
    total = 0
    prefix = bytearray()

    try:
        with temporary.open("xb") as output:
            async for chunk in _read_chunks(reader):
                total += len(chunk)
                if total > max_bytes:
                    raise UploadValidationError(f"Upload exceeds the {max_bytes}-byte size limit")
                if len(prefix) < 16:
                    prefix.extend(chunk[: 16 - len(prefix)])
                output.write(chunk)

        if total == 0:
            raise UploadValidationError("Upload is empty")
        if not _signature_matches(source_type, bytes(prefix)):
            raise UploadValidationError(
                f"Uploaded content is not a valid {source_type.value.upper()} file"
            )

        destination = storage.publish_temporary(
            job_id,
            temporary_filename,
            destination_filename,
        )
    except UploadValidationError:
        raise
    except Exception as error:
        raise UploadValidationError("Upload was interrupted before completion") from error
    finally:
        temporary.unlink(missing_ok=True)

    return UploadReceipt(
        path=destination,
        display_name=_safe_display_name(original_filename, source_type),
        size_bytes=total,
    )


async def _read_chunks(reader: UploadReader) -> AsyncIterator[bytes]:
    while True:
        chunk = await reader.read(64 * 1024)
        if not isinstance(chunk, bytes):
            raise TypeError("upload reader must return bytes")
        if not chunk:
            return
        yield chunk


def _signature_matches(source_type: SourceType, prefix: bytes) -> bool:
    if source_type is SourceType.MP3:
        return prefix.startswith(b"ID3") or (
            len(prefix) >= 2 and prefix[0] == 0xFF and prefix[1] & 0xE0 == 0xE0
        )
    return len(prefix) >= 12 and prefix[4:8] == b"ftyp"


def _safe_display_name(value: str, source_type: SourceType) -> str:
    leaf = value.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    cleaned = "".join(character for character in leaf if character.isprintable())
    cleaned = cleaned.strip().strip(".")
    return cleaned[:128] or f"upload.{source_type.value}"


def parse_youtube_url(value: str) -> YouTubeSource:
    try:
        parsed = urlparse(value.strip())
        port = parsed.port
    except ValueError as error:
        raise ValueError("Enter a valid YouTube video URL") from error

    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username
        or parsed.password
        or port is not None
    ):
        raise ValueError("Enter a valid YouTube video URL")

    host = parsed.hostname.lower()
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "list" in query:
        raise ValueError("YouTube playlists are not supported in Phase 1")

    if host in _YOUTUBE_HOSTS and parsed.path == "/watch":
        video_values = query.get("v", [])
        video_id = video_values[0] if len(video_values) == 1 else ""
    elif host == _SHORT_HOST:
        path_parts = [part for part in parsed.path.split("/") if part]
        video_id = path_parts[0] if len(path_parts) == 1 else ""
    else:
        video_id = ""

    if _VIDEO_ID.fullmatch(video_id) is None:
        raise ValueError("Enter a supported YouTube watch or short URL")

    return YouTubeSource(
        video_id=video_id,
        canonical_url=f"https://www.youtube.com/watch?v={video_id}",
    )
