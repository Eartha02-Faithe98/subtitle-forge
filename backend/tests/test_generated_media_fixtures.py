from pathlib import Path

import av
import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "media"


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    [
        ("spoken-english.mp3", "mp3"),
        ("spoken-english.mp4", "mp4"),
    ],
)
def test_generated_speech_fixture_is_small_and_decodable(
    filename: str,
    expected_format: str,
) -> None:
    path = FIXTURE_ROOT / filename

    assert path.is_file()
    assert 1_000 < path.stat().st_size < 200_000
    with av.open(str(path)) as container:
        assert expected_format in container.format.name.split(",")
        assert len(container.streams.audio) == 1
        frames = list(container.decode(audio=0))

    assert frames
    assert sum(frame.samples for frame in frames) > 16_000
