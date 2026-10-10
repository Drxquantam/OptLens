"""Shared helpers: build fake runner JSON without touching Docker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
COMBOS = [(cc, opt) for cc in ("gcc", "clang") for opt in ("O0", "O2", "O3")]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def run(
    stdout: str = "ok\n",
    exit_code: int | None = 0,
    signal: str | None = None,
    timed_out: bool = False,
    stderr: str = "",
) -> dict[str, Any]:
    return {
        "exit_code": exit_code, "signal": signal, "timed_out": timed_out,
        "output_limit_exceeded": False, "cpu_limit_exceeded": False,
        "duration_ms": 1.5, "stdout": stdout, "stdout_truncated": False,
        "stdout_sha256": sha(stdout), "stderr": stderr, "stderr_truncated": False,
    }


def build(
    cc: str, opt: str, *, compile_ok: bool = True, compile_stderr: str = "",
    r: dict[str, Any] | None = None, reruns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "compiler": cc, "opt": opt,
        "compile": {"ok": compile_ok, "command": f"{cc} -{opt} prog.c", "exit_code": 0 if compile_ok else 1,
                    "timed_out": False, "duration_ms": 10.0, "stderr": compile_stderr},
        "asm": "main:\n\tpush rbp\n\tret\n" if compile_ok else None,
        "asm_truncated": False,
        "run": (r or run()) if compile_ok else None,
        "reruns": reruns or [],
    }


def rerun_of(r: dict[str, Any]) -> dict[str, Any]:
    return {k: r[k] for k in ("stdout_sha256", "exit_code", "signal", "timed_out", "duration_ms")}


def sanitizer(name: str, report: str = "", compiled: bool = True, exit_code: int = 0) -> dict[str, Any]:
    return {
        "name": name,
        "compile": {"ok": compiled, "command": "clang ...", "exit_code": 0, "timed_out": False,
                    "duration_ms": 50.0, "stderr": ""},
        "run": run(stdout="", exit_code=exit_code, stderr=report) if compiled else None,
    }


def raw_output(
    builds: list[dict[str, Any]] | None = None,
    sanitizers: list[dict[str, Any]] | None = None,
    remarks: str = "",
) -> dict[str, Any]:
    return {
        "runner_version": "1",
        "toolchain": {"gcc": "gcc 13", "clang": "clang 18"},
        "limits": {"run_timeout_s": 2.0},
        "builds": builds if builds is not None else [build(cc, opt) for cc, opt in COMBOS],
        "sanitizers": sanitizers if sanitizers is not None else [sanitizer("asan+ubsan"), sanitizer("msan")],
        "remarks": {"command": "clang -O3 ...", "ok": True, "raw": remarks, "truncated": False},
    }


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def fixture_loader():
    return load_fixture
