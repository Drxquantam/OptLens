"""Turn raw runner JSON into the public AnalysisResult."""

from __future__ import annotations

from typing import Any

from .asm import clean_asm, count_instructions
from .models import (
    AnalysisResult,
    BuildOutcome,
    BuildStatus,
    RawBuild,
    RawRun,
    RunnerOutput,
    SanitizerFinding,
    SanitizerOutcome,
)
from .remarks import parse_remarks
from .sanitizers import parse_sanitizer_report, parse_ub_warnings
from .verdict import decide

Signature = tuple[str, int | None, str | None, bool]


def _signature(run: RawRun) -> Signature:
    return (run.stdout_sha256, run.exit_code, run.signal, run.timed_out or run.cpu_limit_exceeded)


def _status(build: RawBuild) -> BuildStatus:
    run = build.run
    if not build.compile.ok or run is None:
        return "compile_error"
    if run.timed_out or run.cpu_limit_exceeded:
        return "timeout"
    if run.output_limit_exceeded:
        return "output_limit"
    if run.signal:
        return "crashed"
    return "ok"


def _build_outcomes(raw: RunnerOutput) -> list[BuildOutcome]:
    # Assign behaviour groups: biggest group first, ties broken by build order.
    sigs: dict[Signature, list[int]] = {}
    for i, b in enumerate(raw.builds):
        if b.run is not None:
            sigs.setdefault(_signature(b.run), []).append(i)
    ordered = sorted(sigs.values(), key=lambda idx: (-len(idx), idx[0]))
    group_of = {i: g for g, idx in enumerate(ordered) for i in idx}

    outcomes = []
    for i, b in enumerate(raw.builds):
        run = b.run
        deterministic = None
        if run is not None and b.reruns:
            base = _signature(run)
            deterministic = all(
                (r.stdout_sha256, r.exit_code, r.signal, r.timed_out) == base for r in b.reruns
            )
        asm = clean_asm(b.asm) if b.asm is not None else None
        outcomes.append(BuildOutcome(
            id=f"{b.compiler}-{b.opt}",
            compiler=b.compiler,
            opt=b.opt,
            status=_status(b),
            compile_ok=b.compile.ok,
            compile_timed_out=b.compile.timed_out,
            compile_command=b.compile.command,
            compile_stderr=b.compile.stderr,
            compile_ms=b.compile.duration_ms,
            exit_code=run.exit_code if run else None,
            signal=run.signal if run else None,
            stdout=run.stdout if run else "",
            stdout_truncated=run.stdout_truncated if run else False,
            stderr=run.stderr if run else "",
            output_hash=run.stdout_sha256[:12] if run else None,
            runtime_ms=run.duration_ms if run else None,
            group=group_of.get(i),
            deterministic=deterministic,
            rerun_count=len(b.reruns),
            asm=asm,
            asm_truncated=b.asm_truncated,
            asm_instructions=count_instructions(asm) if asm is not None else None,
        ))
    return outcomes


def _sanitizer_outcomes(raw: RunnerOutput) -> list[SanitizerOutcome]:
    out = []
    for s in raw.sanitizers:
        run = s.run
        report = run.stderr if run else ""
        out.append(SanitizerOutcome(
            name=s.name,
            compiled=s.compile.ok,
            compile_stderr=s.compile.stderr,
            exit_code=run.exit_code if run else None,
            signal=run.signal if run else None,
            timed_out=bool(run and run.timed_out),
            report=report,
            findings=parse_sanitizer_report(report),
        ))
    return out


def _warnings(raw: RunnerOutput) -> list[SanitizerFinding]:
    seen: set[tuple[object, ...]] = set()
    out = []
    for b in raw.builds:
        for w in parse_ub_warnings(b.compile.stderr):
            key = (w.kind, w.line, w.message)
            if key not in seen:
                seen.add(key)
                out.append(w)
    return out


def analyze(raw_json: dict[str, Any]) -> AnalysisResult:
    raw = RunnerOutput.model_validate(raw_json)
    builds = _build_outcomes(raw)
    sanitizers = _sanitizer_outcomes(raw)
    warnings = _warnings(raw)
    remarks, truncated = parse_remarks(raw.remarks.raw)
    return AnalysisResult(
        verdict=decide(builds, sanitizers, warnings),
        builds=builds,
        sanitizers=sanitizers,
        remarks=remarks,
        remarks_truncated=truncated or raw.remarks.truncated,
        warnings=warnings,
        toolchain=raw.toolchain,
        limits=raw.limits,
    )
