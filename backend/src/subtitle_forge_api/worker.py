"""Bounded single-worker in-process queue for blocking local pipelines."""

import asyncio
from collections.abc import Callable
from typing import Protocol

from subtitle_forge_api.pipeline import PipelineRequest


class PipelineRunner(Protocol):
    def run(self, request: PipelineRequest) -> object: ...


WorkerErrorCallback = Callable[[PipelineRequest, Exception], None]
WorkerDiscardCallback = Callable[[PipelineRequest], None]


class WorkerStateError(RuntimeError):
    pass


class SingleWorkerQueue:
    def __init__(
        self,
        *,
        runner: PipelineRunner,
        on_error: WorkerErrorCallback | None = None,
        on_discard: WorkerDiscardCallback | None = None,
    ) -> None:
        self._runner = runner
        self._on_error = on_error or _ignore_error
        self._on_discard = on_discard or _ignore_discard
        self._queue: asyncio.Queue[PipelineRequest | None] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._accepting = False
        self._stopping = False
        self._pending_count = 0

    @property
    def pending_count(self) -> int:
        return self._pending_count

    async def start(self) -> None:
        if self._task is not None:
            raise WorkerStateError("worker queue is already started")
        self._accepting = True
        self._stopping = False
        self._task = asyncio.create_task(
            self._run(),
            name="subtitle-forge-single-worker",
        )

    async def submit(self, request: PipelineRequest) -> None:
        if not self._accepting or self._task is None:
            raise WorkerStateError("worker queue is not accepting jobs")
        self._pending_count += 1
        await self._queue.put(request)

    async def wait_until_idle(self) -> None:
        await self._queue.join()

    async def shutdown(self) -> None:
        task = self._task
        if task is None:
            return
        self._accepting = False
        self._stopping = True
        while True:
            try:
                pending = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                if pending is not None:
                    self._pending_count -= 1
                    _call_discard(self._on_discard, pending)
            finally:
                self._queue.task_done()
        await self._queue.put(None)
        await task
        self._task = None

    async def _run(self) -> None:
        while True:
            request = await self._queue.get()
            try:
                if request is None:
                    return
                self._pending_count -= 1
                if self._stopping:
                    _call_discard(self._on_discard, request)
                    continue
                try:
                    await asyncio.to_thread(self._runner.run, request)
                except Exception as error:
                    _call_error(self._on_error, request, error)
            finally:
                self._queue.task_done()


def _call_error(
    callback: WorkerErrorCallback,
    request: PipelineRequest,
    error: Exception,
) -> None:
    try:
        callback(request, error)
    except Exception:
        return


def _call_discard(
    callback: WorkerDiscardCallback,
    request: PipelineRequest,
) -> None:
    try:
        callback(request)
    except Exception:
        return


def _ignore_error(request: PipelineRequest, error: Exception) -> None:
    del request, error


def _ignore_discard(request: PipelineRequest) -> None:
    del request
