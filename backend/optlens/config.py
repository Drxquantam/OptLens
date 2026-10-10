"""Runtime configuration, read from OPTLENS_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"OPTLENS_{name}", default)


@dataclass(frozen=True)
class Settings:
    # Sandbox container
    sandbox_image: str = field(default_factory=lambda: _env("SANDBOX_IMAGE", "optlens-sandbox:latest"))
    docker_bin: str = field(default_factory=lambda: _env("DOCKER_BIN", "docker"))
    memory: str = field(default_factory=lambda: _env("MEMORY", "768m"))
    cpus: str = field(default_factory=lambda: _env("CPUS", "2"))
    pids_limit: int = field(default_factory=lambda: int(_env("PIDS_LIMIT", "128")))
    tmpfs_mb: int = field(default_factory=lambda: int(_env("TMPFS_MB", "96")))
    # Docker's default seccomp allowlist plus personality(ADDR_NO_RANDOMIZE) for MSan.
    # Set OPTLENS_SECCOMP_PROFILE="" to fall back to Docker's built-in default.
    seccomp_profile: str = field(
        default_factory=lambda: _env("SECCOMP_PROFILE", str(_REPO_ROOT / "sandbox" / "seccomp.json"))
    )
    job_timeout_s: float = field(default_factory=lambda: float(_env("JOB_TIMEOUT_S", "180")))
    max_result_bytes: int = field(
        default_factory=lambda: int(_env("MAX_RESULT_BYTES", str(16 * 1024 * 1024)))
    )

    # Per-step limits forwarded to the runner (the runner clamps them again).
    compile_timeout_s: float = field(default_factory=lambda: float(_env("COMPILE_TIMEOUT_S", "30")))
    run_timeout_s: float = field(default_factory=lambda: float(_env("RUN_TIMEOUT_S", "2")))
    output_cap_bytes: int = field(default_factory=lambda: int(_env("OUTPUT_CAP_BYTES", str(16 * 1024))))

    # Input validation
    max_source_bytes: int = field(default_factory=lambda: int(_env("MAX_SOURCE_BYTES", str(64 * 1024))))
    max_stdin_bytes: int = field(default_factory=lambda: int(_env("MAX_STDIN_BYTES", str(16 * 1024))))

    # Capacity
    workers: int = field(default_factory=lambda: int(_env("WORKERS", "2")))
    max_queue: int = field(default_factory=lambda: int(_env("MAX_QUEUE", "16")))
    rate_limit: int = field(default_factory=lambda: int(_env("RATE_LIMIT", "10")))
    rate_window_s: float = field(default_factory=lambda: float(_env("RATE_WINDOW_S", "60")))
    trusted_proxies: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            p.strip() for p in _env("TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if p.strip()
        )
    )

    # Storage
    db_path: Path = field(
        default_factory=lambda: Path(
            _env("DB_PATH", str(_REPO_ROOT / "backend" / "data" / "optlens.sqlite3"))
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        )
    )

    def runner_limits(self) -> dict[str, float]:
        return {
            "compile_timeout_s": self.compile_timeout_s,
            "run_timeout_s": self.run_timeout_s,
            "output_cap_bytes": self.output_cap_bytes,
        }
