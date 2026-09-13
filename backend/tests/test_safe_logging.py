import logging

from subtitle_forge_api.domain import ErrorCategory, JobStage
from subtitle_forge_api.safe_logging import JobEventLogger


def test_structured_job_log_contains_only_safe_operational_fields(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("subtitle_forge_test")
    caplog.set_level(logging.INFO, logger=logger.name)
    dangerous = RuntimeError(
        "https://user:password@example/?token=secret "
        "C:\\private\\audio.wav prompt=private raw_provider_response"
    )

    JobEventLogger(logger).record(
        job_id="00000000-0000-0000-0000-000000000001",
        stage=JobStage.TRANSLATING,
        provider="ollama token=secret",
        duration_ms=1_234,
        error=dangerous,
    )

    record = caplog.records[-1]
    assert record.message == "subtitle_forge_job_event"
    assert record.job_id == "00000000-0000-0000-0000-000000000001"
    assert record.stage == "TRANSLATING"
    assert record.provider == "unknown"
    assert record.duration_ms == 1_234
    assert record.error_category == ErrorCategory.UNEXPECTED.value
    serialized = repr(record.__dict__).lower()
    for secret in (
        "password",
        "token=secret",
        "c:\\private",
        "prompt=private",
        "raw_provider_response",
    ):
        assert secret not in serialized


def test_known_local_provider_and_success_are_recorded_without_error(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("subtitle_forge_success_test")
    caplog.set_level(logging.INFO, logger=logger.name)

    JobEventLogger(logger).record(
        job_id="00000000-0000-0000-0000-000000000002",
        stage=JobStage.TRANSCRIBING,
        provider="local_whisper",
        duration_ms=25,
    )

    record = caplog.records[-1]
    assert record.provider == "local_whisper"
    assert record.error_category is None


def test_invalid_identifiers_and_negative_durations_are_safely_normalized(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("subtitle_forge_normalize_test")
    caplog.set_level(logging.INFO, logger=logger.name)

    JobEventLogger(logger).record(
        job_id="C:\\private\\job-id",
        stage=JobStage.EXTRACTING_AUDIO,
        provider="ffmpeg",
        duration_ms=-100,
    )

    record = caplog.records[-1]
    assert record.job_id == "invalid"
    assert record.duration_ms == 0
    assert "private" not in repr(record.__dict__).lower()
