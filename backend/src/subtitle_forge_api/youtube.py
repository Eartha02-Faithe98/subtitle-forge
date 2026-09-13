"""Contained yt-dlp adapter for one public Phase 1 YouTube video."""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, cast

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

from subtitle_forge_api.intake import parse_youtube_url
from subtitle_forge_api.storage import ManagedJobStorage

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_SUPPORTED_SUFFIXES = {".m4a", ".mp4"}


class YouTubeAcquisitionError(ValueError):
    """Safe acquisition error suitable for user-facing guidance."""


class YoutubeDLClient(Protocol):
    def __enter__(self) -> "YoutubeDLClient": ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def extract_info(self, url: str, *, download: bool) -> object: ...


YdlFactory = Callable[[dict[str, Any]], YoutubeDLClient]


def create_youtube_dl(options: dict[str, Any]) -> YoutubeDLClient:
    return cast(YoutubeDLClient, YoutubeDL(options))


@dataclass(frozen=True)
class YouTubeDownload:
    path: Path
    video_id: str
    title: str
    duration_ms: int


class YouTubeDownloader:
    def __init__(
        self,
        *,
        timeout_seconds: int = 60,
        ydl_factory: YdlFactory = create_youtube_dl,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._ydl_factory = ydl_factory

    def download(
        self,
        *,
        storage: ManagedJobStorage,
        job_id: str,
        url: str,
    ) -> YouTubeDownload:
        canonical_url = parse_youtube_url(url).canonical_url
        destination = storage.resolve_member(job_id, "source.mp4")
        job_path = destination.parent
        output_template = job_path / "source.youtube.%(ext)s"
        options: dict[str, Any] = {
            "format": "bestaudio[ext=m4a]/best[ext=mp4]",
            "outtmpl": str(output_template),
            "noplaylist": True,
            "playlist_items": "1",
            "socket_timeout": self._timeout_seconds,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
        }
        completed = False
        try:
            with self._ydl_factory(options) as downloader:
                raw_info = downloader.extract_info(canonical_url, download=True)
            info = _validate_info(raw_info, job_path)
            candidates = _download_candidates(job_path)
            if not candidates:
                raise YouTubeAcquisitionError("YouTube download did not produce a usable output")
            if len(candidates) != 1:
                raise YouTubeAcquisitionError("YouTube download did not produce one safe output")
            downloaded = candidates[0]
            if downloaded.suffix.lower() not in _SUPPORTED_SUFFIXES:
                raise YouTubeAcquisitionError("YouTube did not provide a supported format")

            published = storage.publish_temporary(
                job_id,
                downloaded.name,
                destination.name,
            )
            completed = True
            return YouTubeDownload(
                path=published,
                video_id=info["video_id"],
                title=info["title"],
                duration_ms=info["duration_ms"],
            )
        except YouTubeAcquisitionError:
            raise
        except TimeoutError as error:
            raise YouTubeAcquisitionError("YouTube network request timed out") from error
        except Exception as error:
            message = str(error).lower()
            if "private" in message:
                safe_message = "YouTube video is not publicly accessible"
            elif "removed" in message or "unavailable" in message:
                safe_message = "YouTube video is unavailable"
            else:
                safe_message = "YouTube network request failed"
            raise YouTubeAcquisitionError(safe_message) from error
        finally:
            if not completed:
                _cleanup_download_files(job_path)


def _validate_info(raw_info: object, job_path: Path) -> dict[str, Any]:
    if not isinstance(raw_info, dict):
        raise YouTubeAcquisitionError("YouTube returned invalid metadata")
    if raw_info.get("_type") in {"playlist", "multi_video"} or "entries" in raw_info:
        raise YouTubeAcquisitionError("YouTube source must be a single video")

    video_id = raw_info.get("id")
    title = raw_info.get("title")
    duration = raw_info.get("duration")
    if (
        not isinstance(video_id, str)
        or _VIDEO_ID.fullmatch(video_id) is None
        or not isinstance(title, str)
        or not title.strip()
        or not isinstance(duration, (int, float))
        or not math.isfinite(float(duration))
        or float(duration) <= 0
    ):
        raise YouTubeAcquisitionError("YouTube returned invalid metadata")

    _validate_reported_paths(raw_info, job_path)
    safe_title = "".join(character for character in title if character.isprintable())
    return {
        "video_id": video_id,
        "title": safe_title.strip()[:200] or "YouTube video",
        "duration_ms": round(float(duration) * 1_000),
    }


def _validate_reported_paths(info: dict[object, object], job_path: Path) -> None:
    reported: list[str] = []
    filename = info.get("_filename")
    if isinstance(filename, str):
        reported.append(filename)
    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for item in requested:
            if isinstance(item, dict):
                filepath = item.get("filepath")
                if isinstance(filepath, str):
                    reported.append(filepath)

    for value in reported:
        resolved = Path(value).resolve()
        if resolved.parent != job_path or not resolved.name.startswith("source.youtube."):
            raise YouTubeAcquisitionError("YouTube downloader did not use a safe output path")


def _download_candidates(job_path: Path) -> list[Path]:
    return sorted(
        path
        for path in job_path.glob("source.youtube.*")
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}
    )


def _cleanup_download_files(job_path: Path) -> None:
    for path in job_path.glob("source.youtube.*"):
        if path.is_file():
            path.unlink(missing_ok=True)
