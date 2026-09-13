from pathlib import Path
from typing import Any

import pytest

from subtitle_forge_api.storage import ManagedJobStorage
from subtitle_forge_api.youtube import (
    YouTubeAcquisitionError,
    YouTubeDownloader,
)


class FakeYoutubeDL:
    def __init__(
        self,
        options: dict[str, Any],
        *,
        info: object | None,
        error: Exception | None,
        output_suffix: str | None,
    ) -> None:
        self.options = options
        self.info = info
        self.error = error
        self.output_suffix = output_suffix
        self.calls: list[tuple[str, bool]] = []

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def extract_info(self, url: str, *, download: bool) -> object:
        self.calls.append((url, download))
        if self.output_suffix is not None:
            template = str(self.options["outtmpl"])
            output = Path(template.replace("%(ext)s", self.output_suffix))
            output.write_bytes(b"downloaded-media")
        if self.error is not None:
            raise self.error
        assert self.info is not None
        return self.info


class FakeFactory:
    def __init__(
        self,
        *,
        info: object | None = None,
        error: Exception | None = None,
        output_suffix: str | None = "m4a",
    ) -> None:
        self.info = info
        self.error = error
        self.output_suffix = output_suffix
        self.instances: list[FakeYoutubeDL] = []

    def __call__(self, options: dict[str, Any]) -> FakeYoutubeDL:
        instance = FakeYoutubeDL(
            options,
            info=self.info,
            error=self.error,
            output_suffix=self.output_suffix,
        )
        self.instances.append(instance)
        return instance


def video_info(**overrides: object) -> dict[str, object]:
    info: dict[str, object] = {
        "id": "dQw4w9WgXcQ",
        "title": "Fixture video",
        "duration": 12.5,
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    info.update(overrides)
    return info


def test_downloads_one_public_video_to_server_controlled_path(tmp_path: Path) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    factory = FakeFactory(info=video_info())

    result = YouTubeDownloader(
        timeout_seconds=23,
        ydl_factory=factory,
    ).download(
        storage=storage,
        job_id=job.job_id,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )

    assert result.path == storage.resolve_member(job.job_id, "source.mp4")
    assert result.path.read_bytes() == b"downloaded-media"
    assert result.video_id == "dQw4w9WgXcQ"
    assert result.title == "Fixture video"
    assert result.duration_ms == 12_500
    instance = factory.instances[0]
    assert instance.calls == [("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True)]
    assert instance.options["noplaylist"] is True
    assert instance.options["playlist_items"] == "1"
    assert instance.options["socket_timeout"] == 23
    assert instance.options["format"] == "bestaudio[ext=m4a]/best[ext=mp4]"
    assert Path(str(instance.options["outtmpl"])).parent == result.path.parent
    assert list(result.path.parent.glob("source.youtube.*")) == []


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (FakeFactory(error=TimeoutError("private details")), "network"),
        (FakeFactory(error=RuntimeError("Private video")), "not publicly accessible"),
        (FakeFactory(error=RuntimeError("Video unavailable: removed")), "unavailable"),
        (
            FakeFactory(info={"_type": "playlist", "entries": [video_info()]}),
            "single video",
        ),
        (FakeFactory(info=video_info(id="invalid")), "invalid metadata"),
        (FakeFactory(info=video_info(), output_suffix=None), "output"),
        (FakeFactory(info=video_info(), output_suffix="webm"), "supported format"),
    ],
)
def test_download_maps_failures_safely_and_cleans_partial_files(
    tmp_path: Path,
    factory: FakeFactory,
    message: str,
) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()

    with pytest.raises(YouTubeAcquisitionError, match=message) as captured:
        YouTubeDownloader(ydl_factory=factory).download(
            storage=storage,
            job_id=job.job_id,
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )

    assert "private details" not in str(captured.value)
    assert str(storage.root) not in str(captured.value)
    assert list(job.path.iterdir()) == []


def test_rejects_downloader_metadata_that_points_outside_managed_storage(
    tmp_path: Path,
) -> None:
    storage = ManagedJobStorage(tmp_path / "jobs")
    job = storage.create_job()
    outside = tmp_path / "outside.m4a"
    factory = FakeFactory(info=video_info(_filename=str(outside)))

    with pytest.raises(YouTubeAcquisitionError, match="safe output"):
        YouTubeDownloader(ydl_factory=factory).download(
            storage=storage,
            job_id=job.job_id,
            url="https://youtu.be/dQw4w9WgXcQ",
        )

    assert outside.exists() is False
    assert list(job.path.iterdir()) == []
