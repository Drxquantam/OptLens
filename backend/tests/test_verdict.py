from __future__ import annotations

from conftest import COMBOS, build, raw_output, rerun_of, run, sanitizer

from optlens.analysis import analyze
from optlens.models import Verdict

UBSAN_REPORT = (
    "prog.c:8:14: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'\n"
    "SUMMARY: UndefinedBehaviorSanitizer: signed-integer-overflow prog.c:8:14 \n"
)


def builds_with(outputs: dict[str, dict]) -> list[dict]:
    """All six builds print 'ok' except the ids overridden in `outputs`."""
    return [build(cc, opt, r=outputs.get(f"{cc}-{opt}")) for cc, opt in COMBOS]


def test_all_agree_is_match():
    res = analyze(raw_output())
    assert res.verdict.verdict is Verdict.MATCH
    assert res.verdict.groups == [[f"{cc}-{opt}" for cc, opt in COMBOS]]
    assert all(b.group == 0 and b.status == "ok" for b in res.builds)


def test_consistent_nonzero_exit_still_matches():
    res = analyze(raw_output(builds_with({k: run(exit_code=3) for k in
                                          [f"{c}-{o}" for c, o in COMBOS]})))
    assert res.verdict.verdict is Verdict.MATCH
    assert "non-zero code (3)" in res.verdict.details[0]


def test_mismatch_with_ubsan_is_ub():
    builds = builds_with({"gcc-O0": run("0\n"), "clang-O0": run("0\n"),
                          "gcc-O2": run("1\n"), "gcc-O3": run("1\n"),
                          "clang-O2": run("1\n"), "clang-O3": run("1\n")})
    res = analyze(raw_output(builds, [sanitizer("asan+ubsan", UBSAN_REPORT), sanitizer("msan")]))
    v = res.verdict
    assert v.verdict is Verdict.MISMATCH_UB
    assert "line 8" in v.explanation and "signed integer overflow" in v.explanation
    assert v.evidence[0].kind == "signed-integer-overflow"
    # Majority group first.
    assert v.groups == [["gcc-O2", "gcc-O3", "clang-O2", "clang-O3"], ["gcc-O0", "clang-O0"]]
    assert {b.id: b.group for b in res.builds}["gcc-O0"] == 1


def test_mismatch_clean_and_deterministic_is_suspected_bug():
    bad = run("42\n")
    builds = [build(cc, opt, r=bad if (cc, opt) == ("gcc", "O3") else run("41\n"),
                    reruns=[rerun_of(bad if (cc, opt) == ("gcc", "O3") else run("41\n"))] * 3)
              for cc, opt in COMBOS]
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.MISMATCH_SUSPECTED_COMPILER_BUG
    assert res.verdict.groups[1] == ["gcc-O3"]
    assert "3 extra runs" in res.verdict.explanation
    assert all(b.deterministic for b in res.builds)


def test_flaky_binary_is_nondeterministic_not_compiler_bug():
    first, other = run("1\n"), run("2\n")
    builds = [build(cc, opt, r=first if opt == "O0" else other,
                    reruns=[rerun_of(other)] * 3 if (cc, opt) == ("clang", "O0") else
                    [rerun_of(first if opt == "O0" else other)] * 3)
              for cc, opt in COMBOS]
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.NONDETERMINISTIC
    assert "clang-O0" in res.verdict.explanation


def test_ub_compiler_warning_counts_as_evidence_when_sanitizers_silent():
    warn = "prog.c:14:12: warning: 'value' is used uninitialized [-Wuninitialized]\n"
    builds = [build(cc, opt, compile_stderr=warn if cc == "gcc" else "",
                    r=run("1337\n") if opt == "O0" else run("42\n"),
                    reruns=[rerun_of(run("1337\n") if opt == "O0" else run("42\n"))] * 3)
              for cc, opt in COMBOS]
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.MISMATCH_UB
    assert res.verdict.evidence[0].sanitizer == "compiler-warning"
    assert res.warnings[0].line == 14


def test_ub_warning_alone_does_not_change_match():
    warn = "prog.c:3:5: warning: 'x' is used uninitialized [-Wuninitialized]\n"
    res = analyze(raw_output([build(cc, opt, compile_stderr=warn) for cc, opt in COMBOS]))
    assert res.verdict.verdict is Verdict.MATCH
    assert len(res.warnings) == 1


def test_agree_but_sanitizer_finds_ub_is_latent():
    report = (
        "==1==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffc at pc 0x5 bp 0x7 sp 0x8\n"
        "READ of size 4 at 0x7ffc thread T0\n"
        "    #0 0x55d0c in sum /work/prog.c:10:18\n"
        "    #1 0x55d0d in main /work/prog.c:17:5\n"
    )
    res = analyze(raw_output(sanitizers=[sanitizer("asan+ubsan", report, exit_code=86), sanitizer("msan")]))
    assert res.verdict.verdict is Verdict.LATENT_UB
    f = res.verdict.evidence[0]
    assert (f.sanitizer, f.kind, f.line, f.column) == ("ASan", "stack-buffer-overflow", 10, 18)
    assert "READ of size 4" in f.message


def test_compile_error_everywhere():
    err = "prog.c:3:5: error: expected ';' before 'return'\n"
    res = analyze(raw_output([build(cc, opt, compile_ok=False, compile_stderr=err) for cc, opt in COMBOS]))
    assert res.verdict.verdict is Verdict.COMPILE_ERROR
    assert "6 of 6" in res.verdict.explanation
    assert res.verdict.details == ["prog.c:3:5: error: expected ';' before 'return'"]
    assert all(b.status == "compile_error" and b.group is None for b in res.builds)


def test_partial_compile_error_mentions_extension():
    builds = [build(cc, opt, compile_ok=(cc == "gcc"), compile_stderr="" if cc == "gcc" else
                    "prog.c:1:1: error: nested functions are not supported\n") for cc, opt in COMBOS]
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.COMPILE_ERROR
    assert "compiler-specific" in res.verdict.explanation


def test_compile_timeout_is_not_blamed_on_the_code():
    builds = [build(cc, opt, compile_ok=(cc == "gcc")) for cc, opt in COMBOS]
    for b in builds:
        if b["compiler"] == "clang":
            b["compile"]["timed_out"] = True
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.TIMEOUT
    assert res.verdict.title == "Compilation timed out"
    assert "clang-O0" in res.verdict.explanation


def test_all_timeouts():
    t = run("", exit_code=None, signal="SIGKILL", timed_out=True)
    res = analyze(raw_output(builds_with({f"{c}-{o}": t for c, o in COMBOS})))
    assert res.verdict.verdict is Verdict.TIMEOUT
    assert all(b.status == "timeout" for b in res.builds)


def test_slow_O0_with_agreeing_fast_builds_is_timeout_not_bug():
    t = run("", exit_code=None, signal="SIGKILL", timed_out=True)
    builds = [build(cc, opt, r=t if opt == "O0" else run("done\n"),
                    reruns=[rerun_of(t if opt == "O0" else run("done\n"))] * 3)
              for cc, opt in COMBOS]
    res = analyze(raw_output(builds))
    assert res.verdict.verdict is Verdict.TIMEOUT
    assert "gcc-O0" in res.verdict.explanation


def test_consistent_crash_is_runtime_error():
    crash = run("", exit_code=None, signal="SIGSEGV")
    res = analyze(raw_output(builds_with({f"{c}-{o}": crash for c, o in COMBOS})))
    assert res.verdict.verdict is Verdict.RUNTIME_ERROR
    assert "SIGSEGV" in res.verdict.title


def test_missing_sanitizer_build_is_reported():
    res = analyze(raw_output(sanitizers=[sanitizer("asan+ubsan"), sanitizer("msan", compiled=False)]))
    assert res.verdict.verdict is Verdict.MATCH
    assert any("msan" in d for d in res.verdict.details)


def test_real_runner_fixture_signed_overflow(fixture_loader):
    """A fixture captured from the real sandbox for the signed-overflow preset."""
    res = analyze(fixture_loader("signed_overflow.json"))
    assert res.verdict.verdict is Verdict.MISMATCH_UB
    assert any(f.sanitizer == "UBSan" for f in res.verdict.evidence)


def test_real_runner_fixture_clean(fixture_loader):
    res = analyze(fixture_loader("clean_match.json"))
    assert res.verdict.verdict is Verdict.MATCH
    assert {b.asm_instructions is not None for b in res.builds} == {True}
