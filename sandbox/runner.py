#!/usr/bin/env python3
"""OptLens sandbox runner.

Runs *inside* the sandbox container. Reads one job as JSON on stdin:

    {"source": "...", "stdin": "...", "limits": {...optional overrides...}}

compiles the program with every compiler/optimisation combination, runs the
binaries under resource limits, builds sanitizer variants, collects assembly
and Clang optimisation remarks, and prints exactly one JSON document on stdout.

The runner only reports raw facts. All interpretation (verdicts, remark
parsing, assembly cleanup) happens in the backend so it can be unit tested.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

RUNNER_VERSION = "1"
WORK = os.environ.get("OPTLENS_WORKDIR", "/work")
SRC = "prog.c"

COMPILERS = ["gcc", "clang"]
OPT_LEVELS = ["O0", "O2", "O3"]
COMMON_FLAGS = ["-std=gnu17", "-Wall", "-Wextra", "-fno-diagnostics-color"]

# Hard ceilings: the backend may ask for less, never for more.
HARD_LIMITS = {
    "compile_timeout_s": 45.0,
    "run_timeout_s": 5.0,
    "sanitizer_timeout_s": 15.0,
    "output_cap_bytes": 64 * 1024,
    "file_size_bytes": 4 * 1024 * 1024,
    "compile_file_size_bytes": 64 * 1024 * 1024,
    "asm_max_lines": 6000,
    "remarks_cap_bytes": 512 * 1024,
    "reruns": 5,
}
DEFAULT_LIMITS = {
    "compile_timeout_s": 30.0,
    "run_timeout_s": 2.0,
    "sanitizer_timeout_s": 8.0,
    "output_cap_bytes": 16 * 1024,
    "file_size_bytes": 1024 * 1024,
    "compile_file_size_bytes": 48 * 1024 * 1024,
    "asm_max_lines": 4000,
    "remarks_cap_bytes": 256 * 1024,
    "reruns": 3,
}

SANITIZERS = [
    {
        "name": "asan+ubsan",
        "flags": ["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=undefined,address"],
        "env": {
            "ASAN_OPTIONS": "detect_leaks=0:symbolize=1:abort_on_error=0:exitcode=86",
            "UBSAN_OPTIONS": "print_stacktrace=1:report_error_type=1:halt_on_error=0",
        },
    },
    {
        "name": "msan",
        # -O0: at -O1 Clang already folds many uninitialised reads into constants
        # before MSan instrumentation runs, hiding exactly the bugs we look for.
        "flags": [
            "-O0", "-g", "-fno-omit-frame-pointer",
            "-fsanitize=memory", "-fsanitize-memory-track-origins=2",
        ],
        "env": {"MSAN_OPTIONS": "symbolize=1:exitcode=87"},
    },
]


def clamp_limits(requested: dict[str, Any] | None) -> dict[str, Any]:
    limits = dict(DEFAULT_LIMITS)
    for key, value in (requested or {}).items():
        if key in HARD_LIMITS and isinstance(value, (int, float)) and value > 0:
            limits[key] = type(HARD_LIMITS[key])(min(value, HARD_LIMITS[key]))
    return limits


def read_capped(path: str, cap: int) -> tuple[str, bool, str]:
    """Return (text, truncated, sha256-of-full-content)."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        data = b""
    digest = hashlib.sha256(data).hexdigest()
    truncated = len(data) > cap
    return data[:cap].decode("utf-8", errors="replace"), truncated, digest


def run_limited(
    cmd: list[str],
    *,
    timeout: float,
    tag: str,
    limits: dict[str, Any],
    stdin_path: str | None = None,
    env_extra: dict[str, str] | None = None,
    cpu_limit: bool = True,
) -> dict[str, Any]:
    """Run a command in its own process group with rlimits and a wall clock."""
    out_path = os.path.join(WORK, f".{tag}.out")
    err_path = os.path.join(WORK, f".{tag}.err")
    fsize = int(limits["file_size_bytes"])

    def preexec() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        if cpu_limit:
            cpu = int(timeout) + 1
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))

    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": WORK}
    env.update(env_extra or {})

    stdin_fh = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    timed_out = False
    start = time.perf_counter()
    try:
        with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
            proc = subprocess.Popen(
                cmd, cwd=WORK, stdin=stdin_fh, stdout=out_fh, stderr=err_fh,
                env=env, preexec_fn=preexec, start_new_session=True,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
    finally:
        if stdin_path:
            stdin_fh.close()  # type: ignore[union-attr]
    duration_ms = (time.perf_counter() - start) * 1000.0

    # Clean up any stragglers left in the process group.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass

    cap = int(limits["output_cap_bytes"])
    stdout, stdout_trunc, stdout_hash = read_capped(out_path, cap)
    stderr, stderr_trunc, _ = read_capped(err_path, cap)
    rc = proc.returncode
    sig = -rc if rc is not None and rc < 0 else None
    return {
        "exit_code": rc if rc is not None and rc >= 0 else None,
        "signal": signal.Signals(sig).name if sig else None,
        "timed_out": timed_out,
        "output_limit_exceeded": sig == signal.SIGXFSZ,
        "cpu_limit_exceeded": sig == signal.SIGXCPU,
        "duration_ms": round(duration_ms, 3),
        "stdout": stdout,
        "stdout_truncated": stdout_trunc,
        "stdout_sha256": stdout_hash,
        "stderr": stderr,
        "stderr_truncated": stderr_trunc,
    }


def compile_step(cmd: list[str], tag: str, limits: dict[str, Any]) -> dict[str, Any]:
    # Sanitizer-instrumented binaries are several MB, so compiles get a larger
    # file-size limit than user programs (tmpfs size still bounds the total).
    res = run_limited(
        cmd, timeout=limits["compile_timeout_s"], tag=tag,
        limits={**limits, "file_size_bytes": limits["compile_file_size_bytes"]},
    )
    return {
        "ok": res["exit_code"] == 0 and not res["timed_out"],
        "command": " ".join(cmd),
        "exit_code": res["exit_code"],
        "timed_out": res["timed_out"],
        "duration_ms": res["duration_ms"],
        "stderr": res["stderr"],
    }


def tool_version(cmd: str) -> str:
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
        return out.stdout.splitlines()[0].strip() if out.stdout else "unknown"
    except Exception:  # pragma: no cover - diagnostic only
        return "unknown"


def main() -> int:
    job = json.load(sys.stdin)
    source: str = job["source"]
    stdin_text: str = job.get("stdin") or ""
    limits = clamp_limits(job.get("limits"))

    with open(os.path.join(WORK, SRC), "w", encoding="utf-8") as fh:
        fh.write(source)
    stdin_path = os.path.join(WORK, ".stdin")
    with open(stdin_path, "w", encoding="utf-8") as fh:
        fh.write(stdin_text)

    combos = [(cc, opt) for cc in COMPILERS for opt in OPT_LEVELS]

    # --- Compile phase (parallel; compile time is not what we measure) ----------
    def build(combo: tuple[str, str]) -> dict[str, Any]:
        cc, opt = combo
        binary = f"bin_{cc}_{opt}"
        comp = compile_step(
            [cc, f"-{opt}", *COMMON_FLAGS, SRC, "-o", binary, "-lm"], f"c_{cc}_{opt}", limits
        )
        asm_file = f"asm_{cc}_{opt}.s"
        asm_comp = compile_step(
            [cc, f"-{opt}", "-std=gnu17", "-w", "-S", "-masm=intel",
             "-fno-asynchronous-unwind-tables", SRC, "-o", asm_file],
            f"s_{cc}_{opt}", limits,
        )
        asm = None
        asm_truncated = False
        if asm_comp["ok"]:
            with open(os.path.join(WORK, asm_file), encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
            asm_truncated = len(lines) > limits["asm_max_lines"]
            asm = "\n".join(lines[: limits["asm_max_lines"]])
        return {
            "compiler": cc, "opt": opt, "binary": binary, "compile": comp,
            "asm": asm, "asm_truncated": asm_truncated,
        }

    def build_sanitizer(spec: dict[str, Any]) -> dict[str, Any]:
        binary = "bin_" + spec["name"].replace("+", "_")
        comp = compile_step(
            ["clang", *spec["flags"], "-std=gnu17", "-w", "-fno-diagnostics-color",
             SRC, "-o", binary, "-lm"],
            "c_" + binary, limits,
        )
        return {"name": spec["name"], "binary": binary, "compile": comp, "env": spec["env"]}

    def build_remarks() -> dict[str, Any]:
        cmd = ["clang", "-O3", "-gline-tables-only", "-std=gnu17", "-w", "-fno-diagnostics-color",
               "-Rpass=.*", "-Rpass-missed=.*", "-Rpass-analysis=.*", "-c", SRC, "-o", "/dev/null"]
        res = run_limited(
            cmd, timeout=limits["compile_timeout_s"], tag="remarks",
            limits={**limits, "output_cap_bytes": limits["remarks_cap_bytes"]},
        )
        return {
            "command": " ".join(cmd),
            "ok": res["exit_code"] == 0 and not res["timed_out"],
            "raw": res["stderr"],
            "truncated": res["stderr_truncated"],
        }

    t_compile = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        build_futs = [pool.submit(build, c) for c in combos]
        san_futs = [pool.submit(build_sanitizer, s) for s in SANITIZERS]
        remarks_fut = pool.submit(build_remarks)
        builds = [f.result() for f in build_futs]
        sanitizers = [f.result() for f in san_futs]
        remarks = remarks_fut.result()

    # --- Run phase (sequential so runtimes are comparable) ---------------------
    t_run = time.perf_counter()
    for b in builds:
        b["run"] = None
        b["reruns"] = []
        if b["compile"]["ok"]:
            b["run"] = run_limited(
                ["./" + b["binary"]], timeout=limits["run_timeout_s"],
                tag="r_" + b["binary"], limits=limits, stdin_path=stdin_path,
            )

    def signature(run: dict[str, Any]) -> tuple[Any, ...]:
        return (run["stdout_sha256"], run["exit_code"], run["signal"], run["timed_out"])

    ran = [b for b in builds if b["run"] is not None]
    differs = len({signature(b["run"]) for b in ran}) > 1
    if differs:
        # Before anyone blames a compiler, check every binary is deterministic.
        for b in ran:
            for i in range(int(limits["reruns"])):
                r = run_limited(
                    ["./" + b["binary"]], timeout=limits["run_timeout_s"],
                    tag=f"rr_{b['binary']}_{i}", limits=limits, stdin_path=stdin_path,
                )
                b["reruns"].append({
                    "stdout_sha256": r["stdout_sha256"], "exit_code": r["exit_code"],
                    "signal": r["signal"], "timed_out": r["timed_out"],
                    "duration_ms": r["duration_ms"],
                })

    for s in sanitizers:
        s["run"] = None
        if s["compile"]["ok"]:
            # Sanitizer runtimes reserve huge virtual ranges; RLIMIT_CPU is fine,
            # but they need a longer wall clock than plain builds.
            s["run"] = run_limited(
                ["./" + s["binary"]], timeout=limits["sanitizer_timeout_s"],
                tag="r_" + s["binary"], limits=limits, stdin_path=stdin_path,
                env_extra=s["env"],
            )
        del s["env"]
    t_end = time.perf_counter()

    for b in builds:
        del b["binary"]
    for s in sanitizers:
        del s["binary"]

    result = {
        "runner_version": RUNNER_VERSION,
        "toolchain": {"gcc": tool_version("gcc"), "clang": tool_version("clang")},
        "limits": limits,
        "builds": builds,
        "sanitizers": sanitizers,
        "remarks": remarks,
        "timings_ms": {
            "compile": round((t_run - t_compile) * 1000),
            "run": round((t_end - t_run) * 1000),
        },
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report, never crash silently
        json.dump({"runner_version": RUNNER_VERSION, "fatal": f"{type(exc).__name__}: {exc}"}, sys.stdout)
        sys.stdout.write("\n")
        sys.exit(2)
