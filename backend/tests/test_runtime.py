from pathlib import Path

import pytest
from fastapi import FastAPI

from subtitle_forge_api.app import create_local_app
from subtitle_forge_api.domain import JobStage, SourceType
from subtitle_forge_api.persistence import JobRecord, SQLiteJobRepository
from subtitle_forge_api.runtime import build_local_runtime
from subtitle_forge_api.settings import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_root=tmp_path / "data" / "jobs",
    )


@pytest.mark.anyio
async def test_local_runtime_initializes_sqlite_and_recovers_interrupted_jobs(
    tmp_path: Path,
) -> None:
    configured = settings(tmp_path)
    database_path = configured.data_root.parent / "jobs.sqlite3"
    seed = SQLiteJobRepository(database_path)
    seed.initialize()
    seed.create(
        JobRecord(
            job_id="00000000-0000-0000-0000-000000000001",
            source_type=SourceType.MP3,
            stage=JobStage.TRANSCRIBING,
            progress=35,
        )
    )
    seed.close()

    runtime = build_local_runtime(configured)
    await runtime.start()
    recovered = runtime.repository.get("00000000-0000-0000-0000-000000000001")

    assert database_path.is_file()
    assert recovered is not None
    assert recovered.stage is JobStage.FAILED
    assert recovered.error is not None
    assert recovered.error.category.value == "interrupted"

    await runtime.shutdown()
    with pytest.raises(RuntimeError, match="not initialized"):
        runtime.repository.get("00000000-0000-0000-0000-000000000001")


def test_local_app_registers_the_phase_1_routes_and_runtime(tmp_path: Path) -> None:
    application = create_local_app(
        settings(tmp_path),
        readiness_check=lambda configured: {
            "status": "ready",
            "dependencies": {},
        },
    )

    assert isinstance(application, FastAPI)
    paths = {route.path for route in application.routes}
    assert "/health" in paths
    assert "/readiness" in paths
    assert "/api/jobs" in paths
    assert "/api/jobs/{job_id}" in paths
    assert "/api/jobs/{job_id}/artifacts/{artifact_key}" in paths
    assert application.state.local_runtime is not None
