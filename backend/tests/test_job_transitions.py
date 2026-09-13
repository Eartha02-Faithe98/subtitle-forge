import importlib.util

import pytest

from subtitle_forge_api.domain import JobStage, SourceType


def load_jobs():  # type: ignore[no-untyped-def]
    assert importlib.util.find_spec("subtitle_forge_api.jobs") is not None
    from subtitle_forge_api import jobs

    return jobs


@pytest.mark.parametrize("source_type", [SourceType.MP3, SourceType.MP4])
def test_upload_transition_path_skips_downloading(source_type: SourceType) -> None:
    jobs = load_jobs()

    assert jobs.success_path(source_type) == (
        JobStage.PENDING,
        JobStage.EXTRACTING_AUDIO,
        JobStage.TRANSCRIBING,
        JobStage.TRANSLATING,
        JobStage.GENERATING_SUBTITLES,
        JobStage.GENERATING_SUMMARY,
        JobStage.COMPLETED,
    )


def test_youtube_transition_path_includes_downloading() -> None:
    jobs = load_jobs()

    assert jobs.success_path(SourceType.YOUTUBE)[1] is JobStage.DOWNLOADING


@pytest.mark.parametrize("source_type", list(SourceType))
def test_every_success_path_transition_is_valid(source_type: SourceType) -> None:
    jobs = load_jobs()
    path = jobs.success_path(source_type)

    for current, following in zip(path, path[1:], strict=False):
        jobs.ensure_transition(current, following, source_type)


@pytest.mark.parametrize(
    ("current", "following", "source_type"),
    [
        (JobStage.PENDING, JobStage.DOWNLOADING, SourceType.MP3),
        (JobStage.TRANSLATING, JobStage.TRANSCRIBING, SourceType.MP4),
        (JobStage.COMPLETED, JobStage.FAILED, SourceType.YOUTUBE),
        (JobStage.FAILED, JobStage.PENDING, SourceType.MP3),
    ],
)
def test_invalid_backward_and_post_terminal_transitions_are_rejected(
    current: JobStage,
    following: JobStage,
    source_type: SourceType,
) -> None:
    jobs = load_jobs()

    with pytest.raises(ValueError, match="transition"):
        jobs.ensure_transition(current, following, source_type)


def test_any_non_terminal_stage_can_fail_once() -> None:
    jobs = load_jobs()

    for stage in JobStage:
        if stage not in {JobStage.COMPLETED, JobStage.FAILED}:
            jobs.ensure_transition(stage, JobStage.FAILED, SourceType.YOUTUBE)


def test_stage_progress_ranges_are_bounded_and_monotonic() -> None:
    jobs = load_jobs()
    path = jobs.success_path(SourceType.YOUTUBE)
    starts = [jobs.progress_for_stage(stage, 0.0) for stage in path]
    finishes = [jobs.progress_for_stage(stage, 1.0) for stage in path]

    assert starts[0] == 0
    assert finishes[-1] == 100
    assert starts == sorted(starts)
    assert finishes == sorted(finishes)
    assert all(start <= finish for start, finish in zip(starts, finishes, strict=True))
    assert jobs.progress_for_stage(JobStage.TRANSCRIBING, -1) == starts[3]
    assert jobs.progress_for_stage(JobStage.TRANSCRIBING, 2) == finishes[3]
