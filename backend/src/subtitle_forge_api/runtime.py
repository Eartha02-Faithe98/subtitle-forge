"""Production composition for the Phase 1 local-only processing runtime."""

import logging
from pathlib import Path

from subtitle_forge_api.api import JobApiServices
from subtitle_forge_api.artifacts import ArtifactPublisher, Phase1Result
from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.errors import InterruptedProcessingError, SafeJobFailureService
from subtitle_forge_api.jobs import RecoveryReport, recover_on_startup
from subtitle_forge_api.lifecycle import JobLifecycleService
from subtitle_forge_api.media import (
    AudioExtractor,
    MediaInspectionError,
    MediaProbe,
)
from subtitle_forge_api.ollama import OllamaClient
from subtitle_forge_api.persistence import SQLiteJobRepository
from subtitle_forge_api.pipeline import (
    AcquiredMedia,
    PipelineOrchestrator,
    PipelineRequest,
    PreparedMedia,
)
from subtitle_forge_api.safe_logging import JobEventLogger
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.storage import ManagedJobStorage
from subtitle_forge_api.subtitles import build_subtitle_cues
from subtitle_forge_api.summarization import OllamaSummaryProvider
from subtitle_forge_api.translation import OllamaTranslationProvider
from subtitle_forge_api.whisper import FasterWhisperProvider
from subtitle_forge_api.whisper_orchestration import (
    ChunkedWhisperTranscriber,
    FfmpegChunkMaterializer,
)
from subtitle_forge_api.worker import SingleWorkerQueue
from subtitle_forge_api.youtube import YouTubeDownloader


class LocalMediaAcquirer:
    def __init__(self, storage: ManagedJobStorage, downloader: YouTubeDownloader) -> None:
        self._storage = storage
        self._downloader = downloader

    def acquire(self, request: PipelineRequest) -> AcquiredMedia:
        if request.source_type is SourceType.YOUTUBE:
            if request.youtube_url is None:
                raise ValueError("YouTube URL is unavailable")
            downloaded = self._downloader.download(
                storage=self._storage,
                job_id=request.job_id,
                url=request.youtube_url,
            )
            return AcquiredMedia(downloaded.path, SourceType.MP4)

        expected = self._storage.resolve_member(
            request.job_id,
            f"source.{request.source_type.value}",
        )
        if (
            request.source_path is None
            or request.source_path.resolve() != expected
            or not expected.is_file()
        ):
            raise MediaInspectionError("The uploaded media is unavailable")
        return AcquiredMedia(expected, request.source_type)


class LocalMediaPreparer:
    def __init__(
        self,
        storage: ManagedJobStorage,
        probe: MediaProbe,
        extractor: AudioExtractor,
    ) -> None:
        self._storage = storage
        self._probe = probe
        self._extractor = extractor

    def prepare(self, job_id: str, media: AcquiredMedia) -> PreparedMedia:
        inspection = self._probe.inspect(media.path, expected_type=media.media_type)
        audio = self._extractor.prepare(
            storage=self._storage,
            job_id=job_id,
            source_path=media.path,
            source_type=media.media_type,
            inspection=inspection,
        )
        return PreparedMedia(audio.path, inspection.duration_ms)


class ManagedTerminalCleanup:
    def __init__(self, storage: ManagedJobStorage) -> None:
        self._storage = storage

    def cleanup(
        self,
        job_id: str,
        paths: tuple[Path, ...],
        succeeded: bool,
    ) -> None:
        del succeeded
        for path in paths:
            try:
                managed = self._storage.resolve_member(job_id, path.name)
                if managed == path.resolve():
                    managed.unlink(missing_ok=True)
            except (OSError, ValueError):
                continue


class _CapturingPublisher:
    def __init__(self, publisher: ArtifactPublisher) -> None:
        self._publisher = publisher
        self.result: Phase1Result | None = None

    def publish(self, **values: object) -> Phase1Result:
        result = self._publisher.publish(**values)  # type: ignore[arg-type]
        self.result = result
        return result


class LocalPipelineRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: SQLiteJobRepository,
        storage: ManagedJobStorage,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._lifecycle = JobLifecycleService(repository)
        self._acquirer = LocalMediaAcquirer(
            storage,
            YouTubeDownloader(timeout_seconds=settings.youtube_timeout_seconds),
        )
        self._preparer = LocalMediaPreparer(
            storage,
            MediaProbe(timeout_seconds=settings.ffprobe_timeout_seconds),
            AudioExtractor(timeout_seconds=settings.ffmpeg_timeout_seconds),
        )
        self._cleanup = ManagedTerminalCleanup(storage)
        self._event_logger = JobEventLogger(logging.getLogger("subtitle_forge.jobs"))

    def run(self, request: PipelineRequest) -> Phase1Result:
        ollama = OllamaClient(
            base_url=self._settings.ollama_base_url,
            model=self._settings.ollama_model,
            timeout_seconds=self._settings.ollama_timeout_seconds,
            max_prompt_chars=self._settings.prompt_max_chars,
        )
        whisper = FasterWhisperProvider(
            profile=request.whisper_profile,
            model_map=self._settings.whisper_models,
            device=self._settings.whisper_device,
            compute_type=self._settings.whisper_compute_type,
        )
        transcriber = ChunkedWhisperTranscriber(
            provider=whisper,
            max_chunk_ms=self._settings.audio_chunk_seconds * 1_000,
            overlap_ms=self._settings.audio_chunk_overlap_seconds * 1_000,
            materializer=FfmpegChunkMaterializer(
                timeout_seconds=self._settings.ffmpeg_timeout_seconds,
            ),
        )
        capturing_publisher = _CapturingPublisher(ArtifactPublisher(self._storage))

        def report(stage: object, fraction: float) -> None:
            from subtitle_forge_api.domain import JobStage

            if not isinstance(stage, JobStage):
                raise TypeError("pipeline reported an invalid stage")
            artifacts = (
                capturing_publisher.result.artifacts
                if stage is JobStage.COMPLETED and capturing_publisher.result is not None
                else None
            )
            self._lifecycle.report(
                request.job_id,
                stage,
                fraction,
                artifacts=artifacts,
            )

        return PipelineOrchestrator(
            acquirer=self._acquirer,
            preparer=self._preparer,
            transcriber=transcriber,
            translator=OllamaTranslationProvider(
                client=ollama,
                max_batch_chars=min(4_000, self._settings.prompt_max_chars // 2),
            ),
            subtitle_builder=build_subtitle_cues,
            summarizer=OllamaSummaryProvider(
                client=ollama,
                max_batch_chars=min(4_000, self._settings.prompt_max_chars // 2),
                max_reduce_chars=self._settings.prompt_max_chars,
            ),
            publisher=capturing_publisher,
            cleanup=self._cleanup,
            report_progress=report,
            event_logger=self._event_logger,
        ).run(request)


class LocalApplicationRuntime:
    def __init__(
        self,
        *,
        repository: SQLiteJobRepository,
        storage: ManagedJobStorage,
        queue: SingleWorkerQueue,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.queue = queue
        self.recovery_report: RecoveryReport | None = None
        self._started = False

    @property
    def services(self) -> JobApiServices:
        return JobApiServices(self.repository, self.storage, self.queue)

    async def start(self) -> None:
        if self._started:
            raise RuntimeError("local runtime is already started")
        self.repository.initialize()
        try:
            self.recovery_report = recover_on_startup(
                self.repository,
                artifact_exists=self._artifact_exists,
            )
            await self.queue.start()
        except Exception:
            self.repository.close()
            raise
        self._started = True

    async def shutdown(self) -> None:
        try:
            if self._started:
                await self.queue.shutdown()
        finally:
            self.repository.close()
            self._started = False

    def _artifact_exists(self, job_id: str, artifact: object) -> bool:
        from subtitle_forge_api.domain import ArtifactManifestEntry

        if not isinstance(artifact, ArtifactManifestEntry):
            return False
        try:
            path = self.storage.resolve_member(job_id, artifact.filename)
            return path.is_file() and path.stat().st_size == artifact.size_bytes
        except (OSError, ValueError):
            return False


def build_local_runtime(settings: Settings) -> LocalApplicationRuntime:
    storage = ManagedJobStorage(settings.data_root)
    repository = SQLiteJobRepository(settings.data_root.parent / "jobs.sqlite3")
    runner = LocalPipelineRunner(
        settings=settings,
        repository=repository,
        storage=storage,
    )
    failure_service = SafeJobFailureService(repository)

    def fail_job(request: PipelineRequest, error: Exception) -> None:
        failure_service.fail(request.job_id, error)

    def interrupt_job(request: PipelineRequest) -> None:
        failure_service.fail(
            request.job_id,
            InterruptedProcessingError("local application stopped"),
        )

    queue = SingleWorkerQueue(
        runner=runner,
        on_error=fail_job,
        on_discard=interrupt_job,
    )
    return LocalApplicationRuntime(
        repository=repository,
        storage=storage,
        queue=queue,
    )
