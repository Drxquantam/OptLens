"""Pydantic models: the raw runner protocol and the public API schema."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Raw runner protocol (what sandbox/runner.py prints)
# ---------------------------------------------------------------------------


class RawCompile(BaseModel):
    ok: bool
    command: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    duration_ms: float = 0.0
    stderr: str = ""


class RawRun(BaseModel):
    exit_code: int | None = None
    signal: str | None = None
    timed_out: bool = False
    output_limit_exceeded: bool = False
    cpu_limit_exceeded: bool = False
    duration_ms: float = 0.0
    stdout: str = ""
    stdout_truncated: bool = False
    stdout_sha256: str = ""
    stderr: str = ""
    stderr_truncated: bool = False


class RawRerun(BaseModel):
    stdout_sha256: str
    exit_code: int | None = None
    signal: str | None = None
    timed_out: bool = False
    duration_ms: float = 0.0


class RawBuild(BaseModel):
    compiler: str
    opt: str
    compile: RawCompile
    asm: str | None = None
    asm_truncated: bool = False
    run: RawRun | None = None
    reruns: list[RawRerun] = Field(default_factory=list)


class RawSanitizer(BaseModel):
    name: str
    compile: RawCompile
    run: RawRun | None = None


class RawRemarks(BaseModel):
    command: str = ""
    ok: bool = False
    raw: str = ""
    truncated: bool = False


class RunnerOutput(BaseModel):
    runner_version: str
    toolchain: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, float] = Field(default_factory=dict)
    builds: list[RawBuild]
    sanitizers: list[RawSanitizer] = Field(default_factory=list)
    remarks: RawRemarks = Field(default_factory=RawRemarks)


# ---------------------------------------------------------------------------
# Public API schema
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    source: str = Field(min_length=1, description="C source code")
    stdin: str = Field(default="", description="Text fed to the program's standard input")
    preset_id: str | None = Field(default=None, description="Preset the source came from, if any")


class Verdict(StrEnum):
    MATCH = "MATCH"
    LATENT_UB = "LATENT_UB"
    MISMATCH_UB = "MISMATCH_UB"
    MISMATCH_SUSPECTED_COMPILER_BUG = "MISMATCH_SUSPECTED_COMPILER_BUG"
    NONDETERMINISTIC = "NONDETERMINISTIC"
    COMPILE_ERROR = "COMPILE_ERROR"
    TIMEOUT = "TIMEOUT"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


BuildStatus = Literal["ok", "compile_error", "timeout", "crashed", "output_limit"]


class BuildOutcome(BaseModel):
    id: str = Field(description="e.g. 'gcc-O3'")
    compiler: str
    opt: str
    status: BuildStatus
    compile_ok: bool
    compile_timed_out: bool = False
    compile_command: str
    compile_stderr: str
    compile_ms: float
    exit_code: int | None = None
    signal: str | None = None
    stdout: str = ""
    stdout_truncated: bool = False
    stderr: str = ""
    output_hash: str | None = Field(default=None, description="Short SHA-256 of stdout")
    runtime_ms: float | None = None
    group: int | None = Field(
        default=None, description="Behaviour class; builds with equal group behaved identically"
    )
    deterministic: bool | None = Field(
        default=None, description="None when reruns were not needed"
    )
    rerun_count: int = 0
    asm: str | None = None
    asm_truncated: bool = False
    asm_instructions: int | None = None


class SanitizerFinding(BaseModel):
    sanitizer: Literal["UBSan", "ASan", "MSan", "compiler-warning"]
    kind: str
    message: str
    line: int | None = None
    column: int | None = None


class SanitizerOutcome(BaseModel):
    name: str
    compiled: bool
    compile_stderr: str = ""
    exit_code: int | None = None
    signal: str | None = None
    timed_out: bool = False
    report: str = ""
    findings: list[SanitizerFinding] = Field(default_factory=list)


class Remark(BaseModel):
    kind: Literal["passed", "missed", "analysis"]
    pass_name: str
    message: str
    line: int | None = None
    column: int | None = None


class VerdictInfo(BaseModel):
    verdict: Verdict
    title: str
    explanation: str
    details: list[str] = Field(default_factory=list)
    evidence: list[SanitizerFinding] = Field(default_factory=list)
    groups: list[list[str]] = Field(
        default_factory=list, description="Build ids partitioned by identical behaviour"
    )


class AnalysisResult(BaseModel):
    verdict: VerdictInfo
    builds: list[BuildOutcome]
    sanitizers: list[SanitizerOutcome]
    remarks: list[Remark]
    remarks_truncated: bool = False
    warnings: list[SanitizerFinding] = Field(default_factory=list)
    toolchain: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, float] = Field(default_factory=dict)


JobStatus = Literal["queued", "running", "done", "failed"]


class JobInfo(BaseModel):
    id: str
    status: JobStatus
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    queue_position: int | None = None
    preset_id: str | None = None
    source: str | None = None
    stdin: str | None = None
    result: AnalysisResult | None = None
    error: str | None = None


class AnalyzeAccepted(BaseModel):
    job_id: str
    status: JobStatus
    queue_position: int | None = None


class HistoryItem(BaseModel):
    id: str
    created_at: float
    verdict: Verdict
    preset_id: str | None = None
    source_preview: str


class Preset(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    expected_verdict: Verdict
    source: str
    stdin: str = ""


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    docker: bool
    sandbox_image: bool
    image: str
    workers: int
    queued: int
    running: int
