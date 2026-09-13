"""FastAPI application factory."""

import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from subtitle_forge_api.api import JobApiServices, register_job_routes
from subtitle_forge_api.origin_guard import SubmissionOriginMiddleware
from subtitle_forge_api.readiness import check_readiness
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.worker import SingleWorkerQueue

ReadinessCheck = Callable[[Settings], dict[str, object]]


def create_app(
    settings: Settings | None = None,
    readiness_check: ReadinessCheck | None = None,
    worker_queue: SingleWorkerQueue | None = None,
    job_services: JobApiServices | None = None,
    local_runtime: object | None = None,
) -> FastAPI:
    """Create the Subtitle Forge API application."""
    resolved_settings = settings or Settings()
    resolved_readiness_check = readiness_check or check_readiness

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if local_runtime is not None:
            await local_runtime.start()  # type: ignore[attr-defined]
        elif worker_queue is not None:
            await worker_queue.start()
        try:
            yield
        finally:
            if local_runtime is not None:
                await local_runtime.shutdown()  # type: ignore[attr-defined]
            elif worker_queue is not None:
                await worker_queue.shutdown()

    application = FastAPI(title="Subtitle Forge API", lifespan=lifespan)
    readiness_report = resolved_readiness_check(resolved_settings)
    application.state.readiness = readiness_report
    application.state.worker_queue = worker_queue
    application.state.local_runtime = local_runtime
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.add_middleware(
        SubmissionOriginMiddleware,
        allowed_origins=resolved_settings.allowed_origins,
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readiness")
    def readiness() -> dict[str, object]:
        return readiness_report

    @application.get("/api/config")
    def public_config() -> dict[str, str]:
        return {
            "api_version": "1",
            "speech_provider": "Local Whisper",
            "translation_provider": "Ollama-compatible",
            "summary_provider": "Ollama-compatible",
            "ollama_model": _safe_model_label(resolved_settings.ollama_model),
        }

    if job_services is not None:
        register_job_routes(
            application,
            services=job_services,
            settings=resolved_settings,
        )

    return application


def _safe_model_label(value: str) -> str:
    if len(value) > 120 or "\\" in value or re.search(r"(?:api[_-]?key|token|secret)", value, re.I):
        return "configured-local-model"
    return value


def create_local_app(
    settings: Settings | None = None,
    readiness_check: ReadinessCheck | None = None,
) -> FastAPI:
    from subtitle_forge_api.runtime import build_local_runtime

    resolved_settings = settings or Settings()
    runtime = build_local_runtime(resolved_settings)
    return create_app(
        resolved_settings,
        readiness_check=readiness_check,
        worker_queue=runtime.queue,
        job_services=runtime.services,
        local_runtime=runtime,
    )


app = create_local_app()
