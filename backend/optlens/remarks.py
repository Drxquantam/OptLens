"""Parse Clang ``-Rpass`` / ``-Rpass-missed`` / ``-Rpass-analysis`` output."""

from __future__ import annotations

import re

from .models import Remark

SOURCE_FILE = "prog.c"
MAX_REMARKS = 400

# prog.c:5:3: remark: vectorized loop (vectorization width: 4, ...) [-Rpass=loop-vectorize]
_REMARK_RE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+): remark: (?P<msg>.*?)\s*"
    r"\[-Rpass(?P<kind>-missed|-analysis)?=(?P<pass>[^\]]+)\]\s*$"
)
# Remarks without a usable source location, e.g. "remark: ... [-Rpass-analysis=...]".
_NOLOC_RE = re.compile(
    r"^(?:[^:\n]*: )?remark: (?P<msg>.*?)\s*\[-Rpass(?P<kind>-missed|-analysis)?=(?P<pass>[^\]]+)\]\s*$"
)

_KIND = {None: "passed", "-missed": "missed", "-analysis": "analysis"}
# Per-pass IR size bookkeeping: hundreds of lines, no insight for a reader.
NOISY_PASSES = frozenset({"size-info"})


def parse_remarks(raw: str, max_remarks: int = MAX_REMARKS) -> tuple[list[Remark], bool]:
    """Return (remarks, truncated). Only remarks located in the user's file are kept,
    plus location-less ones; caret/snippet lines that Clang prints are ignored."""
    remarks: list[Remark] = []
    seen: set[tuple[object, ...]] = set()
    truncated = False
    for line in raw.splitlines():
        m = _REMARK_RE.match(line)
        if m:
            if m.group("file").rsplit("/", 1)[-1] != SOURCE_FILE:
                continue
            remark = Remark(
                kind=_KIND[m.group("kind")],  # type: ignore[arg-type]
                pass_name=m.group("pass"),
                message=m.group("msg"),
                line=int(m.group("line")) or None,
                column=int(m.group("col")) or None,
            )
        else:
            m2 = _NOLOC_RE.match(line)
            if not m2:
                continue
            remark = Remark(
                kind=_KIND[m2.group("kind")],  # type: ignore[arg-type]
                pass_name=m2.group("pass"),
                message=m2.group("msg"),
            )
        if remark.pass_name in NOISY_PASSES:
            continue
        key = (remark.kind, remark.pass_name, remark.message, remark.line, remark.column)
        if key in seen:
            continue
        seen.add(key)
        if len(remarks) >= max_remarks:
            truncated = True
            break
        remarks.append(remark)
    return remarks, truncated
