"""Curated example programs shown in the UI preset menu."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..models import Preset, Verdict

_DIR = Path(__file__).resolve().parent

_META: list[dict[str, str]] = [
    {
        "id": "vectorize",
        "file": "vectorize.c",
        "title": "Loop vectorization",
        "category": "Optimization",
        "verdict": "MATCH",
        "summary": (
            "A dependence-free saxpy loop over 1024 floats. At -O3 the loop vectorizer packs"
            " four floats into each SIMD register. Open the Assembly Diff: scalar `movss`/`mulss`/"
            "`addss` at -O0 become packed `movaps`/`mulps`/`addps` at -O3, with Clang processing"
            " eight elements per iteration. The Remarks tab shows Clang's \"vectorized loop\""
            " message with the chosen vector width and interleave count."
        ),
    },
    {
        "id": "inlining",
        "file": "inlining.c",
        "title": "Function inlining",
        "category": "Optimization",
        "verdict": "MATCH",
        "summary": (
            "Three tiny helpers (`square`, `add`, `dist2`) called in a loop. At -O2 and above the"
            " inliner pastes their bodies into `main`, removing the call overhead and exposing"
            " the arithmetic to further simplification. Both GCC and Clang then fold the whole"
            " loop to the constant 1285, so `main` just calls `printf`. The Remarks tab lists"
            " every inlining decision with its cost and threshold."
        ),
    },
    {
        "id": "dead-code",
        "file": "dead_code.c",
        "title": "Dead code elimination",
        "category": "Optimization",
        "verdict": "MATCH",
        "summary": (
            "A million-iteration loop whose result is never used, plus a debug branch guarded by"
            " a constant `0`. -O0 dutifully executes all of it; -O2/-O3 delete both, leaving"
            " `main` as little more than a call to `puts`. Compare the instruction counts in the"
            " Assembly Diff tab."
        ),
    },
    {
        "id": "closed-form",
        "file": "closed_form.c",
        "title": "Loop to closed form",
        "category": "Optimization",
        "verdict": "MATCH",
        "summary": (
            "Sums 0..n-1 in a loop. Clang's scalar evolution analysis recognizes the induction"
            " pattern and replaces the loop with the closed-form n(n-1)/2, so the optimized"
            " `triangle` contains no loop at all, just a multiply and a shift. GCC keeps a loop"
            " (unrolled by two); compare `clang-O3` with `gcc-O3` in the Assembly Diff."
        ),
    },
    {
        "id": "signed-overflow",
        "file": "signed_overflow.c",
        "title": "Signed overflow UB (x + 1 > x)",
        "category": "Undefined behaviour",
        "verdict": "MISMATCH_UB",
        "summary": (
            "`x + 1 > x` with `x = INT_MAX`. Signed overflow is undefined behaviour, so the"
            " optimizer may assume it never happens and fold the comparison to `1`. GCC does so"
            " even at -O0, while Clang -O0 really performs the wrapping addition (INT_MIN) and"
            " prints 0. The builds disagree and UBSan pinpoints the overflow: the program is"
            " wrong, not the compiler."
        ),
    },
    {
        "id": "uninitialized",
        "file": "uninitialized.c",
        "title": "Uninitialized variable read",
        "category": "Undefined behaviour",
        "verdict": "MISMATCH_UB",
        "summary": (
            "`pick(0)` returns a local that was never assigned. Unoptimized builds return"
            " whatever happens to be in that stack slot (GCC -O0 picks up the 1337 planted by"
            " `scribble()`), while optimized builds assume the only real path assigns 42."
            " MemorySanitizer reports the uninitialized read and Clang warns about it too."
        ),
    },
    {
        "id": "out-of-bounds",
        "file": "out_of_bounds.c",
        "title": "Out-of-bounds array read",
        "category": "Undefined behaviour",
        "verdict": "MISMATCH_UB",
        "summary": (
            "An off-by-one loop (`i <= n`) reads one element past the end of a 4-element stack"
            " array. What it reads depends entirely on stack layout, which changes with the"
            " optimization level. AddressSanitizer catches it as a stack-buffer-overflow and"
            " reports the exact line of the bad read."
        ),
    },
    {
        "id": "clean-match",
        "file": "clean_match.c",
        "title": "Well-defined program (all match)",
        "category": "Baseline",
        "verdict": "MATCH",
        "stdin": "compiler\n",
        "summary": (
            "FNV-1a hashing of a line read from stdin plus a Collatz search, using only unsigned"
            " arithmetic, bounded loops and initialized data. Every compiler and optimization"
            " level must print exactly the same thing and the sanitizers stay silent: the"
            " MATCH verdict you want to see. Try editing the stdin box."
        ),
    },
]


@lru_cache(maxsize=1)
def load_presets() -> tuple[Preset, ...]:
    return tuple(
        Preset(
            id=m["id"],
            title=m["title"],
            category=m["category"],
            summary=m["summary"],
            expected_verdict=Verdict(m["verdict"]),
            source=(_DIR / m["file"]).read_text(encoding="utf-8"),
            stdin=m.get("stdin", ""),
        )
        for m in _META
    )
