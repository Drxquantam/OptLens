"""In-process job queue with a fixed-size worker pool.

The number of workers is the concurrency cap: at most ``workers`` sandbox
containers run at once, and at most ``max_queue`` jobs wait behind them.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import OrderedDict

from .analysis import analyze
from .models import AnalyzeRequest, JobInfo
from .sandbox import SandboxError, SandboxRunner
from .store import HistoryStore

log = logging.getLogger("optlens.jobs")


class QueueFull(Exception):
    pass


class JobManager:
    def __init__(
        self,
        runner: SandboxRunner,
        store: HistoryStore,
        workers: int = 2,
        max_queue: int = 16,
        keep_in_memory: int = 500,
    ) -> None:
        self.runner = runner
        self.store = store
        self.workers = workers
        self.max_queue = max_queue
        self._keep = keep_in_memory
        self._jobs: OrderedDict[str, JobInfo] = OrderedDict()
        self._queue: asyncio.Queue[str] | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._pending: list[str] = []
        self.running = 0

    async def start(self) -> None:
        self._queue = asyncio.Queue()
        self._tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers)]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    @property
    def queued(self) -> int:
        return len(self._pending)

    def submit(self, req: AnalyzeRequest) -> JobInfo:
        if self._queue is None:
            raise RuntimeError("JobManager not started")
        if len(self._pending) >= self.max_queue:
            raise QueueFull()
        job = JobInfo(
            id=uuid.uuid4().hex, status="queued", created_at=time.time(),
            preset_id=req.preset_id, source=req.source, stdin=req.stdin,
        )
        self._jobs[job.id] = job
        while len(self._jobs) > self._keep:
            self._jobs.popitem(last=False)
        self._pending.append(job.id)
        self._queue.put_nowait(job.id)
        job.queue_position = len(self._pending)
        return job

    def get(self, job_id: str) -> JobInfo | None:
        job = self._jobs.get(job_id)
        if job is None:
            return self.store.get(job_id)
        if job.status == "queued" and job_id in self._pending:
            job.queue_position = self._pending.index(job_id) + 1
        return job

    async def _worker(self, idx: int) -> None:
        assert self._queue is not None
        while True:
            job_id = await self._queue.get()
            try:
                if job_id in self._pending:
                    self._pending.remove(job_id)
                job = self._jobs.get(job_id)
                if job is not None:
                    await self._run(job)
            finally:
                self._queue.task_done()

    async def _run(self, job: JobInfo) -> None:
        job.status = "running"
        job.queue_position = None
        job.started_at = time.time()
        self.running += 1
        try:
            raw = await self.runner.run(job.source or "", job.stdin or "")
            job.result = await asyncio.to_thread(analyze, raw)
            job.status = "done"
        except SandboxError as exc:
            log.warning("job %s: sandbox error: %s", job.id, exc)
            job.status = "failed"
            job.error = str(exc)
        except Exception as exc:  # never kill the worker
            log.exception("job %s crashed", job.id)
            job.status = "failed"
            job.error = f"internal error: {type(exc).__name__}"
        finally:
            self.running -= 1
            job.finished_at = time.time()
        if job.status == "done":
            try:
                await asyncio.to_thread(self.store.save, job)
            except Exception:
                log.exception("failed to persist job %s", job.id)
