"""Decide what a differential run means.

The key distinction: if optimisation levels disagree *and* the program has
undefined behaviour, the compilers are allowed to disagree; the program is
wrong. Only when the program is (as far as we can tell) UB-free, deterministic
and still behaves differently is a compiler bug a reasonable suspicion.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import BuildOutcome, SanitizerFinding, SanitizerOutcome, Verdict, VerdictInfo

LIMITED = ("timeout", "output_limit")


def describe_finding(f: SanitizerFinding) -> str:
    where = f"line {f.line}" if f.line else "unknown line"
    return f"{f.sanitizer} ({f.kind}) at {where}: {f.message}"


def _first_errors(stderr: str, limit: int = 4) -> list[str]:
    errors = [ln.strip() for ln in stderr.splitlines() if "error:" in ln]
    return errors[:limit] or [ln.strip() for ln in stderr.splitlines() if ln.strip()][:limit]


def _behaviour(b: BuildOutcome) -> str:
    if b.status == "timeout":
        return "timed out"
    if b.status == "output_limit":
        return "exceeded the output limit"
    if b.signal:
        return f"crashed ({b.signal})"
    preview = b.stdout.strip().splitlines()[:1]
    out = f'printed "{preview[0][:60]}"' if preview else "printed nothing"
    return f"{out}, exit {b.exit_code}"


def group_ids(builds: Sequence[BuildOutcome]) -> list[list[str]]:
    groups: dict[int, list[str]] = {}
    for b in builds:
        if b.group is not None:
            groups.setdefault(b.group, []).append(b.id)
    return [groups[k] for k in sorted(groups)]


def decide(
    builds: Sequence[BuildOutcome],
    sanitizers: Sequence[SanitizerOutcome],
    ub_warnings: Sequence[SanitizerFinding] = (),
) -> VerdictInfo:
    findings = [f for s in sanitizers for f in s.findings]
    sanitizer_notes = [
        f"The {s.name} build did not compile, so its checks are missing."
        for s in sanitizers if not s.compiled
    ] + [
        f"The {s.name} build hit the time limit, so its checks may be incomplete."
        for s in sanitizers if s.timed_out
    ]

    # 1. Compile errors ---------------------------------------------------------
    failed = [b for b in builds if not b.compile_ok]
    slow = [b for b in failed if b.compile_timed_out]
    if slow:
        names = ", ".join(b.id for b in slow)
        return VerdictInfo(
            verdict=Verdict.TIMEOUT, title="Compilation timed out",
            explanation=(
                f"Compiling {names} exceeded the sandbox compile time limit. Very large or"
                " template-heavy code can do this, but for small programs it usually means the"
                " server is overloaded. Try again in a moment."
            ),
            details=_first_errors(slow[0].compile_stderr),
        )
    if failed:
        names = ", ".join(b.id for b in failed)
        partial = len(failed) < len(builds)
        explanation = (
            f"{len(failed)} of {len(builds)} builds failed to compile ({names})."
            + (" The others succeeded, so the code probably relies on a compiler-specific"
               " extension or behaviour." if partial else " Fix the errors below and run again.")
        )
        return VerdictInfo(
            verdict=Verdict.COMPILE_ERROR, title="Compilation failed",
            explanation=explanation, details=_first_errors(failed[0].compile_stderr),
        )

    groups = group_ids(builds)
    reference = builds[0]

    # 2. Everyone agrees --------------------------------------------------------
    if len(groups) <= 1:
        if all(b.status in LIMITED for b in builds):
            what = "time" if reference.status == "timeout" else "output"
            return VerdictInfo(
                verdict=Verdict.TIMEOUT, title=f"Every build hit the {what} limit",
                explanation=(
                    f"All six builds exceeded the sandbox {what} limit, so there is nothing to"
                    " compare. Reduce the amount of work or output (e.g. smaller loop bounds)."
                ),
                details=sanitizer_notes, evidence=findings, groups=groups,
            )
        if all(b.status == "crashed" for b in builds):
            return VerdictInfo(
                verdict=Verdict.RUNTIME_ERROR, title=f"Every build crashed ({reference.signal})",
                explanation=(
                    "The program crashes the same way at every optimisation level, so the"
                    " optimizer did not change its behaviour, but the program itself is broken."
                    + (f" The sanitizers point at the cause: {describe_finding(findings[0])}."
                       if findings else "")
                ),
                details=sanitizer_notes, evidence=findings, groups=groups,
            )
        if findings:
            return VerdictInfo(
                verdict=Verdict.LATENT_UB, title="Outputs match, but the program has undefined behaviour",
                explanation=(
                    "All builds happened to agree, but the sanitizers found undefined behaviour:"
                    f" {describe_finding(findings[0])}. The agreement is luck: a different"
                    " compiler version, flag or input could legitimately change the result."
                ),
                details=sanitizer_notes, evidence=findings, groups=groups,
            )
        details = list(sanitizer_notes)
        if reference.exit_code not in (0, None):
            details.insert(0, f"Every build exited with the same non-zero code ({reference.exit_code}).")
        return VerdictInfo(
            verdict=Verdict.MATCH, title="All builds agree",
            explanation=(
                "GCC and Clang at -O0, -O2 and -O3 produced identical output and exit codes, and"
                " the sanitizer builds (ASan, UBSan, MSan) reported nothing. The optimizer"
                " preserved this program's behaviour."
            ),
            details=details, groups=groups,
        )

    # 3. Builds disagree ----------------------------------------------------------
    by_id = {b.id: b for b in builds}
    group_lines = [
        f"{' / '.join(ids)}: {_behaviour(by_id[ids[0]])}" for ids in groups
    ]

    if findings:
        top = findings[0]
        return VerdictInfo(
            verdict=Verdict.MISMATCH_UB,
            title="Outputs differ: undefined behaviour in your code",
            explanation=(
                f"The builds disagree, and the sanitizers caught undefined behaviour at line"
                f" {top.line or '?'}: \"{top.message}\" ({top.sanitizer}). When a program has"
                " undefined behaviour the C standard places no requirements on it, so each"
                " optimisation level may legitimately produce something different. This is"
                " almost certainly your code's fault, not the compiler's."
            ),
            details=group_lines + sanitizer_notes, evidence=findings, groups=groups,
        )

    flaky = [b.id for b in builds if b.deterministic is False]
    if flaky:
        return VerdictInfo(
            verdict=Verdict.NONDETERMINISTIC, title="Outputs differ: the program is nondeterministic",
            explanation=(
                f"Re-running the same binaries gave different results ({', '.join(flaky)}),"
                " so the difference is not caused by the optimizer. Typical causes: reading"
                " uninitialised memory, time/rand without a fixed seed, printing addresses."
            ),
            details=group_lines + sanitizer_notes, groups=groups,
        )

    finished = [b for b in builds if b.status not in LIMITED]
    if len(finished) < len(builds) and len({b.group for b in finished}) <= 1:
        slow = ", ".join(b.id for b in builds if b.status in LIMITED)
        return VerdictInfo(
            verdict=Verdict.TIMEOUT, title="Some builds hit a resource limit",
            explanation=(
                f"{slow} exceeded the sandbox limits while the remaining builds finished and"
                " agree with each other. That usually means the slower builds are just too"
                " slow, not that they compute something different."
            ),
            details=group_lines + sanitizer_notes, groups=groups,
        )

    if ub_warnings:
        top = ub_warnings[0]
        return VerdictInfo(
            verdict=Verdict.MISMATCH_UB,
            title="Outputs differ: the compiler warned about undefined behaviour",
            explanation=(
                "The sanitizers stayed silent, but the compiler warned at line"
                f" {top.line}: \"{top.message}\" ({top.kind}). That warning describes undefined"
                " behaviour, which is the most likely reason the builds disagree."
            ),
            details=group_lines + sanitizer_notes, evidence=list(ub_warnings), groups=groups,
        )

    reruns = max((b.rerun_count for b in builds), default=0)
    return VerdictInfo(
        verdict=Verdict.MISMATCH_SUSPECTED_COMPILER_BUG,
        title="Outputs differ with clean sanitizers: candidate compiler bug",
        explanation=(
            "The builds disagree, ASan/UBSan/MSan reported nothing, and every binary gave the"
            f" same result over {reruns} extra runs. That makes this a candidate compiler bug."
            " Sanitizers cannot see every kind of UB (strict aliasing, unsequenced"
            " modifications, some evaluation-order issues), so reduce the test case and"
            " double-check before reporting it."
        ),
        details=group_lines + sanitizer_notes, groups=groups,
    )
