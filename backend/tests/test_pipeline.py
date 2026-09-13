from pathlib import Path
from typing import Literal, cast

import pytest

from subtitle_forge_api.artifacts import Phase1Result
from subtitle_forge_api.domain import (
    JobStage,
    SourceType,
    Summary,
    Transcript,
    TranscriptSegment,
    TranslatedSegment,
    TranslatedTranscript,
)
from subtitle_forge_api.pipeline import (
    AcquiredMedia,
    PipelineOrchestrator,
    PipelineRequest,
    PreparedMedia,
)


class FakePipelineDependencies:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events: list[str] = []
        self.publish_error: Exception | None = None
        self.cleanup_calls: list[tuple[tuple[Path, ...], bool]] = []
        self.acquired = root / "source.mp4"
        self.prepared = root / "audio.wav"
        self.acquired.write_bytes(b"media")
        self.prepared.write_bytes(b"audio")
        self.transcript = Transcript(
            segments=(
                TranscriptSegment(segment_id="s1", start_ms=0, end_ms=1_000, source_text="Hello."),
            )
        )
        self.translated = TranslatedTranscript(
            segments=(
                TranslatedSegment(
                    segment_id="s1", start_ms=0, end_ms=1_000, translated_text="哈囉。"
                ),
            )
        )

    def acquire(self, request: PipelineRequest) -> AcquiredMedia:
        self.events.append("acquire")
        media_type = (
            SourceType.MP4 if request.source_type is SourceType.YOUTUBE else request.source_type
        )
        return AcquiredMedia(path=self.acquired, media_type=media_type)

    def prepare(self, job_id: str, media: AcquiredMedia) -> PreparedMedia:
        del job_id, media
        self.events.append("prepare")
        return PreparedMedia(path=self.prepared, duration_ms=1_000)

    def transcribe(self, audio_path: Path, duration_ms: int, progress=None) -> Transcript:  # type: ignore[no-untyped-def]
        del audio_path, duration_ms
        self.events.append("transcribe")
        if progress is not None:
            progress(0.5)
        return self.transcript

    def translate(self, transcript: Transcript) -> TranslatedTranscript:
        assert transcript is self.transcript
        self.events.append("translate")
        return self.translated

    def build_subtitles(self, transcript: Transcript) -> None:
        assert transcript is self.transcript
        self.events.append("subtitles")

    def summarize(self, transcript: Transcript, language: Literal["en", "zh-TW"]) -> Summary:
        assert transcript is self.transcript
        self.events.append(f"summary-{language}")
        return Summary(language=language, text=f"{language} summary")

    def publish(self, **values: object) -> Phase1Result:
        assert values["transcript"] is self.transcript
        assert values["translated"] is self.translated
        self.events.append("publish")
        if self.publish_error is not None:
            raise self.publish_error
        return cast(Phase1Result, object())

    def cleanup(self, job_id: str, paths: tuple[Path, ...], succeeded: bool) -> None:
        del job_id
        self.cleanup_calls.append((paths, succeeded))
        self.events.append("cleanup")


@pytest.mark.parametrize("source_type", [SourceType.YOUTUBE, SourceType.MP3, SourceType.MP4])
def test_pipeline_runs_exact_stage_and_capability_order(
    tmp_path: Path,
    source_type: SourceType,
) -> None:
    dependencies = FakePipelineDependencies(tmp_path)
    observed_stages: list[JobStage] = []
    progress: list[tuple[JobStage, float]] = []
    request = PipelineRequest(
        job_id="00000000-0000-0000-0000-000000000001",
        source_type=source_type,
        source_path=None
        if source_type is SourceType.YOUTUBE
        else tmp_path / f"source.{source_type.value}",
        youtube_url="https://youtu.be/dQw4w9WgXcQ" if source_type is SourceType.YOUTUBE else None,
    )
    orchestrator = PipelineOrchestrator(
        acquirer=dependencies,
        preparer=dependencies,
        transcriber=dependencies,
        translator=dependencies,
        subtitle_builder=dependencies.build_subtitles,
        summarizer=dependencies,
        publisher=dependencies,
        cleanup=dependencies,
        report_progress=lambda stage, fraction: (
            observed_stages.append(stage)
            if not observed_stages or observed_stages[-1] is not stage
            else None,
            progress.append((stage, fraction)),
        ),
    )

    orchestrator.run(request)

    expected = [
        *([JobStage.DOWNLOADING] if source_type is SourceType.YOUTUBE else []),
        JobStage.EXTRACTING_AUDIO,
        JobStage.TRANSCRIBING,
        JobStage.TRANSLATING,
        JobStage.GENERATING_SUBTITLES,
        JobStage.GENERATING_SUMMARY,
        JobStage.COMPLETED,
    ]
    assert observed_stages == expected
    assert dependencies.events == [
        "acquire",
        "prepare",
        "transcribe",
        "translate",
        "subtitles",
        "summary-en",
        "summary-zh-TW",
        "publish",
        "cleanup",
    ]
    assert (JobStage.TRANSCRIBING, 0.5) in progress
    assert dependencies.cleanup_calls == [((dependencies.acquired, dependencies.prepared), True)]


def test_pipeline_failure_cleans_intermediates_without_reporting_completed(
    tmp_path: Path,
) -> None:
    dependencies = FakePipelineDependencies(tmp_path)
    dependencies.publish_error = RuntimeError("publication failed")
    stages: list[JobStage] = []
    orchestrator = PipelineOrchestrator(
        acquirer=dependencies,
        preparer=dependencies,
        transcriber=dependencies,
        translator=dependencies,
        subtitle_builder=dependencies.build_subtitles,
        summarizer=dependencies,
        publisher=dependencies,
        cleanup=dependencies,
        report_progress=lambda stage, fraction: stages.append(stage),
    )

    with pytest.raises(RuntimeError, match="publication failed"):
        orchestrator.run(
            PipelineRequest(
                job_id="00000000-0000-0000-0000-000000000001",
                source_type=SourceType.MP4,
                source_path=tmp_path / "source.mp4",
            )
        )

    assert JobStage.COMPLETED not in stages
    assert dependencies.cleanup_calls == [((dependencies.acquired, dependencies.prepared), False)]


def test_pipeline_records_structured_events_at_real_capability_boundaries(
    tmp_path: Path,
) -> None:
    dependencies = FakePipelineDependencies(tmp_path)
    events: list[tuple[JobStage, str, int, Exception | None]] = []

    class EventRecorder:
        def record(
            self,
            *,
            job_id: str,
            stage: JobStage,
            provider: str,
            duration_ms: int,
            error: Exception | None = None,
        ) -> None:
            assert job_id == "00000000-0000-0000-0000-000000000001"
            events.append((stage, provider, duration_ms, error))

    orchestrator = PipelineOrchestrator(
        acquirer=dependencies,
        preparer=dependencies,
        transcriber=dependencies,
        translator=dependencies,
        subtitle_builder=dependencies.build_subtitles,
        summarizer=dependencies,
        publisher=dependencies,
        cleanup=dependencies,
        report_progress=lambda stage, fraction: None,
        event_logger=EventRecorder(),
    )

    orchestrator.run(
        PipelineRequest(
            job_id="00000000-0000-0000-0000-000000000001",
            source_type=SourceType.YOUTUBE,
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
        )
    )

    assert [(stage, provider) for stage, provider, _, _ in events] == [
        (JobStage.DOWNLOADING, "yt_dlp"),
        (JobStage.EXTRACTING_AUDIO, "ffmpeg"),
        (JobStage.TRANSCRIBING, "local_whisper"),
        (JobStage.TRANSLATING, "ollama"),
        (JobStage.GENERATING_SUBTITLES, "pipeline"),
        (JobStage.GENERATING_SUMMARY, "ollama"),
        (JobStage.GENERATING_SUMMARY, "ollama"),
        (JobStage.GENERATING_SUMMARY, "pipeline"),
    ]
    assert all(duration_ms >= 0 and error is None for _, _, duration_ms, error in events)
