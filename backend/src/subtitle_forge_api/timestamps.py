"""Timestamp validation and deterministic presentation formatting."""


def validate_timestamp_ms(milliseconds: int) -> int:
    if milliseconds < 0:
        raise ValueError("timestamp must be non-negative")
    return milliseconds


def validate_interval_ms(start_ms: int, end_ms: int) -> tuple[int, int]:
    validate_timestamp_ms(start_ms)
    validate_timestamp_ms(end_ms)
    if end_ms <= start_ms:
        raise ValueError("end timestamp must be greater than start timestamp")
    return start_ms, end_ms


def _parts(milliseconds: int) -> tuple[int, int, int, int]:
    remaining = validate_timestamp_ms(milliseconds)
    hours, remaining = divmod(remaining, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    seconds, millis = divmod(remaining, 1_000)
    return hours, minutes, seconds, millis


def format_display_timestamp(milliseconds: int) -> str:
    hours, minutes, seconds, _ = _parts(milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_srt_timestamp(milliseconds: int) -> str:
    hours, minutes, seconds, millis = _parts(milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
