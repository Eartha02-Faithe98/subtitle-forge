import asyncio
from pathlib import Path
from threading import Event

import pytest
from httpx import ASGITransport, AsyncClient

from subtitle_forge_api.app import create_app
from subtitle_forge_api.domain import SourceType
from subtitle_forge_api.pipeline import PipelineRequest
from subtitle_forge_api.settings import Settings
from subtitle_forge_api.worker import SingleWorkerQueue


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class BlockingRunner:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls: list[str] = []

    def run(self, request: PipelineRequest) -> object:
        self.calls.append(request.job_id)
        self.started.set()
        self.release.wait(timeout=5)
        return object()


def request(identifier: int, tmp_path: Path) -> PipelineRequest:
    return PipelineRequest(
        job_id=f"00000000-0000-0000-0000-{identifier:012d}",
        source_type=SourceType.MP3,
        source_path=tmp_path / f"source-{identifier}.mp3",
    )


async def wait_for(event: Event) -> None:
    for _ in range(100):
        if event.is_set():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("worker event was not observed")


@pytest.mark.anyio
async def test_single_worker_keeps_second_job_pending_and_event_loop_responsive(
    tmp_path: Path,
) -> None:
    runner = BlockingRunner()
    queue = SingleWorkerQueue(runner=runner)
    await queue.start()
    await queue.submit(request(1, tmp_path))
    await queue.submit(request(2, tmp_path))
    await wait_for(runner.started)

    await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
    assert runner.calls == ["00000000-0000-0000-0000-000000000001"]
    assert queue.pending_count == 1

    runner.release.set()
    await queue.shutdown()
    assert runner.calls == ["00000000-0000-0000-0000-000000000001"]


@pytest.mark.anyio
async def test_fastapi_lifespan_starts_worker_and_health_remains_responsive(
    tmp_path: Path,
) -> None:
    runner = BlockingRunner()
    discarded: list[str] = []
    queue = SingleWorkerQueue(
        runner=runner,
        on_discard=lambda item: discarded.append(item.job_id),
    )
    app = create_app(
        Settings(_env_file=None),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
        worker_queue=queue,
    )

    async with app.router.lifespan_context(app):
        await queue.submit(request(1, tmp_path))
        await queue.submit(request(2, tmp_path))
        await wait_for(runner.started)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await asyncio.wait_for(client.get("/health"), timeout=0.5)
        assert response.json() == {"status": "ok"}
        runner.release.set()

    assert runner.calls == ["00000000-0000-0000-0000-000000000001"]
    assert discarded == ["00000000-0000-0000-0000-000000000002"]


@pytest.mark.anyio
async def test_worker_reports_pipeline_failure_and_continues(tmp_path: Path) -> None:
    failures: list[tuple[str, str]] = []

    class FailingRunner:
        def run(self, item: PipelineRequest) -> object:
            raise RuntimeError(f"failed {item.job_id}")

    queue = SingleWorkerQueue(
        runner=FailingRunner(),
        on_error=lambda item, error: failures.append((item.job_id, type(error).__name__)),
    )
    await queue.start()
    await queue.submit(request(3, tmp_path))
    await queue.wait_until_idle()
    await queue.shutdown()

    assert failures == [("00000000-0000-0000-0000-000000000003", "RuntimeError")]
