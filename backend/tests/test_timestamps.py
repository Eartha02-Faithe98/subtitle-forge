import importlib.util

import pytest


def load_timestamps():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.timestamps") is not None
    from subtitle_forge_api import timestamps

    return timestamps


@pytest.mark.parametrize(
    ("milliseconds", "display", "srt"),
    [
        (0, "00:00:00", "00:00:00,000"),
        (1, "00:00:00", "00:00:00,001"),
        (999, "00:00:00", "00:00:00,999"),
        (1_000, "00:00:01", "00:00:01,000"),
        (3_661_007, "01:01:01", "01:01:01,007"),
        (360_000_001, "100:00:00", "100:00:00,001"),
    ],
)
def test_timestamp_formats_are_stable(
    milliseconds: int,
    display: str,
    srt: str,
) -> None:
    timestamps = load_timestamps()

    assert timestamps.format_display_timestamp(milliseconds) == display
    assert timestamps.format_srt_timestamp(milliseconds) == srt


@pytest.mark.parametrize("milliseconds", [-1, -1_000])
def test_timestamp_formatters_reject_negative_values(milliseconds: int) -> None:
    timestamps = load_timestamps()

    with pytest.raises(ValueError, match="non-negative"):
        timestamps.format_display_timestamp(milliseconds)
    with pytest.raises(ValueError, match="non-negative"):
        timestamps.format_srt_timestamp(milliseconds)


@pytest.mark.parametrize("interval", [(-1, 1), (1, 1), (2, 1)])
def test_interval_validation_rejects_invalid_ranges(interval: tuple[int, int]) -> None:
    timestamps = load_timestamps()

    with pytest.raises(ValueError):
        timestamps.validate_interval_ms(*interval)


def test_interval_validation_returns_a_valid_range() -> None:
    timestamps = load_timestamps()

    assert timestamps.validate_interval_ms(0, 1) == (0, 1)
