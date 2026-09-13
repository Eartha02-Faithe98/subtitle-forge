"""Sequential Phase 1 media-to-artifact pipeline orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol, TypeVar

from subtitle_forge_api.artifacts import Phase1Result
from subtitle_forge_api.domain import (
    JobStage,
    SourceType,
    Summary,
    Transcript,
    TranslatedTranscript,
    WhisperProfile,
)
from subtitle_forge_api.providers import ProgressCallback, SummaryLanguage


@dataclass(frozen=True)
class PipelineRequest:
    job_id: str
    source_type: SourceType
    whisper_profile: WhisperProfile = WhisperProfile.BALANCED
    source_path: Path | None = None
    youtube_url: str | None = None

    def __post_init__(self) -> None:
        if self.source_type is SourceType.YOUTUBE:
            valid = self.youtube_url is not None and self.source_path is None
        else:
            valid = self.source_path is not None and self.youtube_url is None
        if not valid:
            raise ValueError("pipeline request source does not match its source type")


@dataclass(frozen=True)
class AcquiredMedia:
    path: Path
    media_type: SourceType


@dataclass(frozen=True)
class PreparedMedia:
    path: Path
    duration_ms: int

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise ValueError("prepared media duration must be positive")


class MediaAcquirer(Protocol):
    def acquire(self, request: PipelineRequest) -> AcquiredMedia: ...


class MediaPreparer(Protocol):
    def prepare(self, job_id: str, media: AcquiredMedia) -> PreparedMedia: ...


class TranscriptionService(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        *,
        duration_ms: int,
        progress: ProgressCallback | None = None,
    ) -> Transcript: ...


class TranslationService(Protocol):
    def translate(self, transcript: Transcript) -> TranslatedTranscript: ...


class SummaryService(Protocol):
    def summarize(
        self,
        transcript: Transcript,
        language: SummaryLanguage,
    ) -> Summary: ...


class ResultPublisher(Protocol):
    def publish(
        self,
        *,
        job_id: str,
        transcript: Transcript,
        translated: TranslatedTranscript,
        english_summary: Summary,
        chinese_summary: Summary,
    ) -> Phase1Result: ...


class TerminalCleanup(Protocol):
    def cleanup(
        self,
        job_id: str,
        paths: tuple[Path, ...],
        succeeded: bool,
    ) -> None: ...


class PipelineEventLogger(Protocol):
    def record(
        self,
        *,
        job_id: str,
        stage: JobStage,
        provider: str,
        duration_ms: int,
        error: Exception | None = None,
    ) -> None: ...


PipelineProgress = Callable[[JobStage, float], None]
SubtitleBuilder = Callable[[Transcript], object]
_ResultValue = TypeVar("_ResultValue")


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        acquirer: MediaAcquirer,
        preparer: MediaPreparer,
        transcriber: TranscriptionService,
        translator: TranslationService,
        subtitle_builder: SubtitleBuilder,
        summarizer: SummaryService,
        publisher: ResultPublisher,
        cleanup: TerminalCleanup,
        report_progress: PipelineProgress,
        event_logger: PipelineEventLogger | None = None,
    ) -> None:
        self._acquirer = acquirer
        self._preparer = preparer
        self._transcriber = transcriber
        self._translator = translator
        self._subtitle_builder = subtitle_builder
        self._summarizer = summarizer
        self._publisher = publisher
        self._cleanup = cleanup
        self._report = report_progress
        self._event_logger = event_logger

    def run(self, request: PipelineRequest) -> Phase1Result:
        cleanup_paths: list[Path] = []
        cleanup_done = False
        try:
            if request.source_type is SourceType.YOUTUBE:
                self._report(JobStage.DOWNLOADING, 0.0)
            acquired = self._timed(
                request=request,
                stage=(
                    JobStage.DOWNLOADING
                    if request.source_type is SourceType.YOUTUBE
                    else JobStage.EXTRACTING_AUDIO
                ),
                provider=("yt_dlp" if request.source_type is SourceType.YOUTUBE else "pipeline"),
                operation=lambda: self._acquirer.acquire(request),
            )
            cleanup_paths.append(acquired.path)

            self._report(JobStage.EXTRACTING_AUDIO, 0.0)
            prepared = self._timed(
                request=request,
                stage=JobStage.EXTRACTING_AUDIO,
                provider="ffmpeg",
                operation=lambda: self._preparer.prepare(request.job_id, acquired),
            )
            if prepared.path not in cleanup_paths:
                cleanup_paths.append(prepared.path)

            self._report(JobStage.TRANSCRIBING, 0.0)
            transcript = self._timed(
                request=request,
                stage=JobStage.TRANSCRIBING,
                provider="local_whisper",
                operation=lambda: self._transcriber.transcribe(
                    prepared.path,
                    duration_ms=prepared.duration_ms,
                    progress=lambda value: self._report(JobStage.TRANSCRIBING, value),
                ),
            )

            self._report(JobStage.TRANSLATING, 0.0)
            translated = self._timed(
                request=request,
                stage=JobStage.TRANSLATING,
                provider="ollama",
                operation=lambda: self._translator.translate(transcript),
            )

            self._report(JobStage.GENERATING_SUBTITLES, 0.0)
            self._timed(
                request=request,
                stage=JobStage.GENERATING_SUBTITLES,
                provider="pipeline",
                operation=lambda: self._subtitle_builder(transcript),
            )

            self._report(JobStage.GENERATING_SUMMARY, 0.0)
            english_summary = self._timed(
                request=request,
                stage=JobStage.GENERATING_SUMMARY,
                provider="ollama",
                operation=lambda: self._summarizer.summarize(transcript, "en"),
            )
            chinese_summary = self._timed(
                request=request,
                stage=JobStage.GENERATING_SUMMARY,
                provider="ollama",
                operation=lambda: self._summarizer.summarize(transcript, "zh-TW"),
            )

            result = self._timed(
                request=request,
                stage=JobStage.GENERATING_SUMMARY,
                provider="pipeline",
                operation=lambda: self._publisher.publish(
                    job_id=request.job_id,
                    transcript=transcript,
                    translated=translated,
                    english_summary=english_summary,
                    chinese_summary=chinese_summary,
                ),
            )
            self._cleanup.cleanup(request.job_id, tuple(cleanup_paths), True)
            cleanup_done = True
            self._report(JobStage.COMPLETED, 1.0)
            return result
        finally:
            if not cleanup_done:
                self._cleanup.cleanup(
                    request.job_id,
                    tuple(cleanup_paths),
                    False,
                )

    def _timed(
        self,
        *,
        request: PipelineRequest,
        stage: JobStage,
        provider: str,
        operation: Callable[[], _ResultValue],
    ) -> _ResultValue:
        started = perf_counter()
        try:
            result = operation()
        except Exception as error:
            self._record_event(request.job_id, stage, provider, started, error)
            raise
        self._record_event(request.job_id, stage, provider, started)
        return result

    def _record_event(
        self,
        job_id: str,
        stage: JobStage,
        provider: str,
        started: float,
        error: Exception | None = None,
    ) -> None:
        if self._event_logger is None:
            return
        self._event_logger.record(
            job_id=job_id,
            stage=stage,
            provider=provider,
            duration_ms=max(0, round((perf_counter() - started) * 1_000)),
            error=error,
        )
