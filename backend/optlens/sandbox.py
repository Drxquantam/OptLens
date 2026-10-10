"""Launch locked-down sandbox containers via the docker CLI.

The API process never compiles or executes user code itself. Each job gets a
fresh container that is destroyed afterwards (``--rm``).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from typing import Any, Protocol

from .config import Settings

SANDBOX_UID = "10001:10001"


class SandboxError(RuntimeError):
    """The sandbox could not produce a result (not the user's program failing)."""


class SandboxTimeout(SandboxError):
    pass


class SandboxRunner(Protocol):
    async def run(self, source: str, stdin: str) -> dict[str, Any]: ...


def docker_run_args(settings: Settings, container_name: str) -> list[str]:
    """The full `docker run` command line. Kept separate so it can be audited/tested."""
    tmpfs_opts = "rw,exec,nosuid,nodev,uid=10001,gid=10001,mode=0700"
    seccomp = (
        ["--security-opt", f"seccomp={settings.seccomp_profile}"] if settings.seccomp_profile else []
    )
    return [
        settings.docker_bin, "run",
        "--rm", "-i",
        "--name", container_name,
        "--network", "none",
        "--memory", settings.memory,
        "--memory-swap", settings.memory,  # no swap on top of the memory limit
        "--cpus", settings.cpus,
        "--pids-limit", str(settings.pids_limit),
        "--read-only",
        "--tmpfs", f"/work:{tmpfs_opts},size={settings.tmpfs_mb}m",
        "--tmpfs", f"/tmp:{tmpfs_opts},size=32m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        *seccomp,
        "--user", SANDBOX_UID,
        "--ulimit", "nofile=256:256",
        "--ulimit", "core=0:0",
        "--label", "optlens.job=1",
        settings.sandbox_image,
    ]


class DockerSandbox:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, source: str, stdin: str) -> dict[str, Any]:
        # A thread + blocking subprocess works with every asyncio event loop
        # (including the Windows selector loop some servers use).
        return await asyncio.to_thread(self._run_blocking, source, stdin)

    def _run_blocking(self, source: str, stdin: str) -> dict[str, Any]:
        name = f"optlens-{uuid.uuid4().hex[:16]}"
        payload = json.dumps(
            {"source": source, "stdin": stdin, "limits": self.settings.runner_limits()}
        ).encode()
        args = docker_run_args(self.settings, name)
        try:
            proc = subprocess.run(
                args, input=payload, capture_output=True, timeout=self.settings.job_timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            self._force_remove(name)
            raise SandboxTimeout(
                f"sandbox exceeded the {self.settings.job_timeout_s:.0f}s job limit"
            ) from exc
        except FileNotFoundError as exc:
            raise SandboxError("docker CLI not found on the API host") from exc

        if len(proc.stdout) > self.settings.max_result_bytes:
            raise SandboxError("sandbox result exceeded the size cap")
        text = proc.stdout.decode("utf-8", errors="replace").strip()
        if not text:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            raise SandboxError(f"sandbox produced no output (exit {proc.returncode}): {err[:500]}")
        try:
            data = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise SandboxError("sandbox produced malformed JSON") from exc
        if "fatal" in data:
            raise SandboxError(f"sandbox runner failed: {data['fatal']}")
        return data

    def _force_remove(self, name: str) -> None:
        try:
            subprocess.run(
                [self.settings.docker_bin, "rm", "-f", name], capture_output=True, timeout=30
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def check(self) -> tuple[bool, bool]:
        """Return (docker reachable, sandbox image present)."""
        try:
            info = subprocess.run(
                [self.settings.docker_bin, "version", "--format", "{{.Server.Version}}"],
                capture_output=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, False
        if info.returncode != 0:
            return False, False
        img = subprocess.run(
            [self.settings.docker_bin, "image", "inspect", self.settings.sandbox_image],
            capture_output=True, timeout=10,
        )
        return True, img.returncode == 0
