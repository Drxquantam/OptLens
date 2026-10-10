"""FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .jobs import JobManager, QueueFull
from .models import AnalyzeAccepted, AnalyzeRequest, Health, HistoryItem, JobInfo, Preset
from .presets import load_presets
from .ratelimit import RateLimiter, client_ip
from .sandbox import DockerSandbox, SandboxRunner
from .store import HistoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    runner: SandboxRunner | None = None,
    store: HistoryStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    sandbox = DockerSandbox(settings)
    runner = runner or sandbox
    store = store or HistoryStore(settings.db_path)
    jobs = JobManager(runner, store, workers=settings.workers, max_queue=settings.max_queue)
    limiter = RateLimiter(settings.rate_limit, settings.rate_window_s)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await jobs.start()
        yield
        await jobs.stop()
        store.close()

    app = FastAPI(
        title="OptLens API",
        version=__version__,
        description="Differential testing of GCC/Clang optimisation levels in a sandbox.",
        lifespan=lifespan,
    )
    app.state.jobs = jobs
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.post("/api/analyze", response_model=AnalyzeAccepted, status_code=202)
    async def submit(req: AnalyzeRequest, request: Request) -> AnalyzeAccepted | JSONResponse:
        if len(req.source.encode()) > settings.max_source_bytes:
            raise HTTPException(413, f"source exceeds {settings.max_source_bytes // 1024} KiB")
        if len(req.stdin.encode()) > settings.max_stdin_bytes:
            raise HTTPException(413, f"stdin exceeds {settings.max_stdin_bytes // 1024} KiB")
        if "\x00" in req.source:
            raise HTTPException(422, "source contains NUL bytes")

        ip = client_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
            settings.trusted_proxies,
        )
        retry = limiter.check(ip)
        if retry is not None:
            return JSONResponse(
                {"detail": f"rate limit exceeded: {settings.rate_limit} runs per"
                           f" {settings.rate_window_s:.0f}s"},
                status_code=429,
                headers={"Retry-After": str(int(retry) + 1)},
            )
        try:
            job = jobs.submit(req)
        except QueueFull:
            return JSONResponse(
                {"detail": "server busy: the job queue is full, try again shortly"},
                status_code=503, headers={"Retry-After": "10"},
            )
        return AnalyzeAccepted(job_id=job.id, status=job.status, queue_position=job.queue_position)

    @app.get("/api/jobs/{job_id}", response_model=JobInfo)
    async def get_job(job_id: str) -> JobInfo:
        if not (len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id)):
            raise HTTPException(404, "job not found")
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    @app.get("/api/presets", response_model=list[Preset])
    async def presets() -> tuple[Preset, ...]:
        return load_presets()

    @app.get("/api/history", response_model=list[HistoryItem])
    async def history(limit: int = 20) -> list[HistoryItem]:
        return await asyncio.to_thread(store.recent, max(1, min(limit, 100)))

    @app.get("/api/health", response_model=Health)
    async def health() -> Health:
        docker_ok, image_ok = await asyncio.to_thread(sandbox.check)
        return Health(
            status="ok" if docker_ok and image_ok else "degraded",
            docker=docker_ok,
            sandbox_image=image_ok,
            image=settings.sandbox_image,
            workers=jobs.workers,
            queued=jobs.queued,
            running=jobs.running,
        )

    return app


app = create_app()
