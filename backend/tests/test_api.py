from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import Any

import pytest
from conftest import raw_output
from fastapi.testclient import TestClient

from optlens.config import Settings
from optlens.main import create_app
from optlens.ratelimit import RateLimiter, client_ip
from optlens.sandbox import SandboxError, docker_run_args
from optlens.store import HistoryStore

SRC = '#include <stdio.h>\nint main(void){puts("hi");return 0;}\n'


class FakeSandbox:
    def __init__(self, result: dict[str, Any] | Exception | None = None, delay: float = 0.0) -> None:
        self.result = result if result is not None else raw_output()
        self.delay = delay
        self.calls: list[tuple[str, str]] = []
        self.active = 0
        self.max_active = 0

    async def run(self, source: str, stdin: str) -> dict[str, Any]:
        self.calls.append((source, stdin))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            if isinstance(self.result, Exception):
                raise self.result
            return self.result
        finally:
            self.active -= 1


def make_client(sandbox: FakeSandbox | None = None, **overrides: Any) -> tuple[TestClient, FakeSandbox]:
    sandbox = sandbox or FakeSandbox()
    settings = replace(Settings(), **overrides)
    app = create_app(settings=settings, runner=sandbox, store=HistoryStore(":memory:"))
    return TestClient(app), sandbox


def wait_done(client: TestClient, job_id: str, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_analyze_roundtrip_and_history():
    client, sandbox = make_client()
    with client:
        r = client.post("/api/analyze", json={"source": SRC, "stdin": "abc", "preset_id": "clean-match"})
        assert r.status_code == 202
        job = wait_done(client, r.json()["job_id"])
        assert job["status"] == "done"
        assert job["result"]["verdict"]["verdict"] == "MATCH"
        assert len(job["result"]["builds"]) == 6
        assert sandbox.calls == [(SRC, "abc")]

        hist = client.get("/api/history").json()
        assert hist[0]["id"] == job["id"] and hist[0]["verdict"] == "MATCH"
        assert hist[0]["source_preview"].startswith("int main")


def test_sandbox_failure_marks_job_failed():
    client, _ = make_client(FakeSandbox(SandboxError("sandbox produced no output")))
    with client:
        job = wait_done(client, client.post("/api/analyze", json={"source": SRC}).json()["job_id"])
        assert job["status"] == "failed"
        assert "no output" in job["error"]


def test_validation_limits():
    client, sandbox = make_client(max_source_bytes=100, max_stdin_bytes=10)
    with client:
        assert client.post("/api/analyze", json={"source": ""}).status_code == 422
        assert client.post("/api/analyze", json={"source": "x" * 101}).status_code == 413
        assert client.post("/api/analyze", json={"source": "int main;", "stdin": "y" * 11}).status_code == 413
        assert client.post("/api/analyze", json={"source": "int\x00main;"}).status_code == 422
    assert sandbox.calls == []


def test_rate_limit_returns_429():
    client, _ = make_client(rate_limit=2, rate_window_s=60)
    with client:
        codes = [client.post("/api/analyze", json={"source": SRC}).status_code for _ in range(3)]
        assert codes == [202, 202, 429]
        r = client.post("/api/analyze", json={"source": SRC})
        assert int(r.headers["Retry-After"]) > 0


def test_queue_full_returns_503_and_concurrency_is_capped():
    sandbox = FakeSandbox(delay=0.3)
    client, _ = make_client(sandbox, workers=2, max_queue=2, rate_limit=100)
    with client:
        codes = [client.post("/api/analyze", json={"source": SRC}).status_code for _ in range(8)]
        # 2 picked up by workers (maybe), 2 queued, the rest rejected.
        assert codes.count(503) >= 4
        assert codes[:2] == [202, 202]
        time.sleep(1.2)
    assert sandbox.max_active <= 2


def test_unknown_job_404():
    client, _ = make_client()
    with client:
        assert client.get("/api/jobs/" + "0" * 32).status_code == 404
        assert client.get("/api/jobs/not-a-job").status_code == 404


def test_presets_endpoint():
    client, _ = make_client()
    with client:
        presets = client.get("/api/presets").json()
    assert len(presets) == 8
    ids = {p["id"] for p in presets}
    assert {"signed-overflow", "uninitialized", "out-of-bounds", "clean-match"} <= ids
    for p in presets:
        assert p["title"] and p["summary"] and "main" in p["source"]


def test_health_reports_queue(monkeypatch: pytest.MonkeyPatch):
    from optlens import sandbox as sandbox_mod

    monkeypatch.setattr(sandbox_mod.DockerSandbox, "check", lambda self: (True, False))
    client, _ = make_client(workers=3)
    with client:
        body = client.get("/api/health").json()
    assert body["status"] == "degraded" and body["docker"] and not body["sandbox_image"]
    assert body["workers"] == 3


def test_docker_args_are_locked_down():
    args = docker_run_args(Settings(), "optlens-test")
    joined = " ".join(args)
    for flag in ("--network none", "--read-only", "--cap-drop ALL",
                 "--security-opt no-new-privileges", "--user 10001:10001", "--pids-limit",
                 "--memory", "--cpus", "--rm"):
        assert flag in joined, flag
    assert "--privileged" not in joined and "-v" not in args and "--volume" not in args
    assert args[-1] == Settings().sandbox_image


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(2, 10, clock=lambda: now[0])
    assert rl.check("a") is None and rl.check("a") is None
    assert rl.check("a") == pytest.approx(10)
    assert rl.check("b") is None
    now[0] = 10.5
    assert rl.check("a") is None


def test_client_ip_only_trusts_configured_proxies():
    trusted = ("127.0.0.1", "172.16.0.0/12")
    assert client_ip("203.0.113.9", "1.2.3.4", trusted) == "203.0.113.9"  # untrusted peer: ignore XFF
    assert client_ip("127.0.0.1", "1.2.3.4", trusted) == "1.2.3.4"
    assert client_ip("172.18.0.2", "6.6.6.6, 1.2.3.4, 172.18.0.5", trusted) == "1.2.3.4"
    assert client_ip("127.0.0.1", None, trusted) == "127.0.0.1"
