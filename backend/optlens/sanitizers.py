"""Extract structured findings from sanitizer reports and compiler warnings."""

from __future__ import annotations

import re

from .models import SanitizerFinding

_SRC = r"(?:[^\s:]*/)?prog\.c"

# prog.c:6:14: runtime error: signed integer overflow: 2147483647 + 1 cannot be ...
_UBSAN_RE = re.compile(rf"^(?:{_SRC}):(?P<line>\d+):(?P<col>\d+): runtime error: (?P<msg>.+)$")
# SUMMARY: UndefinedBehaviorSanitizer: signed-integer-overflow prog.c:6:14
_UBSAN_SUMMARY_RE = re.compile(
    rf"^SUMMARY: UndefinedBehaviorSanitizer: (?P<kind>[\w-]+) (?:{_SRC}):(?P<line>\d+):(?P<col>\d+)"
)
# ==12==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x... at pc ...
_ASAN_RE = re.compile(r"^==\d+==ERROR: AddressSanitizer: (?P<kind>[\w-]+)(?P<rest>.*)$")
# ==12==WARNING: MemorySanitizer: use-of-uninitialized-value
_MSAN_RE = re.compile(r"^==\d+==WARNING: MemorySanitizer: (?P<kind>[\w-]+)(?P<rest>.*)$")
#   Uninitialized value was created by an allocation of 'value' in the stack frame
_MSAN_ORIGIN_RE = re.compile(r"^\s*Uninitialized value was created by (.+?)\s*$")
# #0 0x55d0c in main /work/prog.c:9:12
_FRAME_RE = re.compile(rf"^\s*#\d+ 0x[0-9a-f]+ in (?P<fn>\S+) (?:{_SRC}):(?P<line>\d+)(?::(?P<col>\d+))?")
# READ of size 4 at 0x7ffd... thread T0
_ACCESS_RE = re.compile(r"^(?P<what>(?:READ|WRITE) of size \d+) at ")

# GCC/Clang warnings that usually mean undefined behaviour.
_UB_WARNINGS = (
    "uninitialized",
    "aggressive-loop-optimizations",
    "array-bounds",
    "stringop-overflow",
    "integer-overflow",
    "overflow",
    "shift-count-overflow",
    "shift-negative-value",
    "div-by-zero",
    "return-type",
    "return-local-addr",
    "return-stack-address",
    "use-after-free",
    "sequence-point",
    "unsequenced",
)
# prog.c:7:12: warning: 'x' is used uninitialized [-Wuninitialized]
_WARNING_RE = re.compile(
    rf"^(?:{_SRC}):(?P<line>\d+):(?P<col>\d+): warning: (?P<msg>.*?)\s*\[-W(?P<flag>[\w=-]+)\]\s*$"
)

MAX_FINDINGS = 20


def _first_user_frame(lines: list[str], start: int) -> tuple[int | None, int | None]:
    for line in lines[start : start + 40]:
        m = _FRAME_RE.match(line)
        if m:
            return int(m.group("line")), int(m.group("col")) if m.group("col") else None
    return None, None


def parse_sanitizer_report(report: str) -> list[SanitizerFinding]:
    lines = report.splitlines()
    findings: list[SanitizerFinding] = []
    ubsan_kinds: dict[tuple[int, int], str] = {}
    for line in lines:
        s = _UBSAN_SUMMARY_RE.match(line)
        if s:
            ubsan_kinds[(int(s.group("line")), int(s.group("col")))] = s.group("kind")

    for i, line in enumerate(lines):
        if m := _UBSAN_RE.match(line):
            ln, col = int(m.group("line")), int(m.group("col"))
            findings.append(SanitizerFinding(
                sanitizer="UBSan",
                kind=ubsan_kinds.get((ln, col), "undefined-behavior"),
                message=m.group("msg").strip(),
                line=ln, column=col,
            ))
        elif m := _ASAN_RE.match(line):
            ln, col = _first_user_frame(lines, i + 1)
            access = next(
                (a.group("what") for a in (_ACCESS_RE.match(x) for x in lines[i + 1 : i + 4]) if a),
                None,
            )
            msg = m.group("kind").replace("-", " ")
            if access:
                msg = f"{msg}: {access}"
            findings.append(SanitizerFinding(
                sanitizer="ASan", kind=m.group("kind"), message=msg, line=ln, column=col,
            ))
        elif m := _MSAN_RE.match(line):
            ln, col = _first_user_frame(lines, i + 1)
            msg = m.group("kind").replace("-", " ")
            origin = next(
                (o.group(1) for o in (_MSAN_ORIGIN_RE.match(x) for x in lines[i + 1 : i + 30]) if o),
                None,
            )
            if origin:
                msg = f"{msg} (created by {origin})"
            findings.append(SanitizerFinding(
                sanitizer="MSan", kind=m.group("kind"), message=msg, line=ln, column=col,
            ))
    return _dedupe(findings)


def parse_ub_warnings(compiler_stderr: str) -> list[SanitizerFinding]:
    """Compiler warnings that hint at undefined behaviour (weaker evidence than sanitizers)."""
    findings = []
    for line in compiler_stderr.splitlines():
        m = _WARNING_RE.match(line)
        if m and any(key in m.group("flag") for key in _UB_WARNINGS):
            findings.append(SanitizerFinding(
                sanitizer="compiler-warning", kind=f"-W{m.group('flag')}",
                message=m.group("msg"), line=int(m.group("line")), column=int(m.group("col")),
            ))
    return _dedupe(findings)


def _dedupe(findings: list[SanitizerFinding]) -> list[SanitizerFinding]:
    seen: set[tuple[object, ...]] = set()
    out = []
    for f in findings:
        key = (f.sanitizer, f.kind, f.line, f.column)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out[:MAX_FINDINGS]
