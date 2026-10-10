from __future__ import annotations

from optlens.asm import clean_asm, count_instructions
from optlens.remarks import parse_remarks
from optlens.sanitizers import parse_sanitizer_report, parse_ub_warnings

REMARKS = """\
prog.c:12:5: remark: vectorized loop (vectorization width: 4, interleaved count: 2) [-Rpass=loop-vectorize]
   12 |     for (int i = 0; i < N; i++)
      |     ^
prog.c:20:12: remark: 'square' inlined into 'main' with (cost=-30, threshold=337) at callsite dist2:2:12; [-Rpass=inline]
prog.c:20:12: remark: 'square' inlined into 'main' with (cost=-30, threshold=337) at callsite dist2:2:12; [-Rpass=inline]
prog.c:22:5: remark: 'printf' not inlined into 'main' because its definition is unavailable [-Rpass-missed=inline]
prog.c:4:0: remark: 18 instructions in function [-Rpass-analysis=asm-printer]
/usr/include/x86_64-linux-gnu/bits/stdio2.h:86:10: remark: something in a header [-Rpass=inline]
remark: location-less remark [-Rpass-analysis=prologepilog]
prog.c:9:1: warning: not a remark [-Wfoo]
"""


def test_parse_remarks_kinds_lines_and_dedupe():
    remarks, truncated = parse_remarks(REMARKS)
    assert not truncated
    assert [(r.kind, r.pass_name, r.line) for r in remarks] == [
        ("passed", "loop-vectorize", 12),
        ("passed", "inline", 20),
        ("missed", "inline", 22),
        ("analysis", "asm-printer", 4),
        ("analysis", "prologepilog", None),
    ]
    assert remarks[0].message == "vectorized loop (vectorization width: 4, interleaved count: 2)"
    assert remarks[0].column == 5
    assert remarks[3].column is None  # column 0 means "no column"


def test_parse_remarks_cap():
    raw = "\n".join(f"prog.c:{i}:1: remark: r{i} [-Rpass=gvn]" for i in range(1, 50))
    remarks, truncated = parse_remarks(raw, max_remarks=10)
    assert len(remarks) == 10 and truncated


def test_parse_remarks_empty():
    assert parse_remarks("") == ([], False)


UBSAN = """\
prog.c:8:14: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
    #0 0x5 in always_bigger /work/prog.c:8:14
SUMMARY: UndefinedBehaviorSanitizer: signed-integer-overflow prog.c:8:14
prog.c:8:14: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
"""

ASAN = """\
=================================================================
==1==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffe at pc 0x55 bp 0x7f sp 0x7e
READ of size 4 at 0x7ffe thread T0
    #0 0x55 in sum /work/prog.c:10:18
    #1 0x56 in main /work/prog.c:17:30
SUMMARY: AddressSanitizer: stack-buffer-overflow /work/prog.c:10:18 in sum
"""

MSAN = """\
==1==WARNING: MemorySanitizer: use-of-uninitialized-value
    #0 0x55 in main /work/prog.c:22:5
    #1 0x7f in __libc_start_call_main
"""


def test_ubsan_report_is_deduplicated_and_typed():
    findings = parse_sanitizer_report(UBSAN)
    assert len(findings) == 1
    f = findings[0]
    assert (f.sanitizer, f.kind, f.line, f.column) == ("UBSan", "signed-integer-overflow", 8, 14)
    assert f.message.startswith("signed integer overflow")


def test_asan_report_uses_first_user_frame():
    (f,) = parse_sanitizer_report(ASAN)
    assert (f.sanitizer, f.kind, f.line, f.column) == ("ASan", "stack-buffer-overflow", 10, 18)
    assert f.message == "stack buffer overflow: READ of size 4"


def test_msan_report():
    (f,) = parse_sanitizer_report(MSAN)
    assert (f.sanitizer, f.kind, f.line) == ("MSan", "use-of-uninitialized-value", 22)


def test_clean_report_has_no_findings():
    assert parse_sanitizer_report("hello\nworld\n") == []


def test_ub_warnings_filter():
    stderr = (
        "prog.c:14:12: warning: 'value' is used uninitialized [-Wuninitialized]\n"
        "prog.c:3:7: warning: unused variable 'y' [-Wunused-variable]\n"
        "prog.c:9:17: warning: 'value' may be used uninitialized [-Wmaybe-uninitialized]\n"
        "prog.c:5:12: warning: variable 'v' is uninitialized when used here [-Wuninitialized]\n"
    )
    found = parse_ub_warnings(stderr)
    assert [(w.kind, w.line) for w in found] == [
        ("-Wuninitialized", 14), ("-Wmaybe-uninitialized", 9), ("-Wuninitialized", 5),
    ]


GCC_ASM = """\
\t.file\t"prog.c"
\t.intel_syntax noprefix
\t.text
\t.section\t.rodata
.LC0:
\t.string\t"x = %d\\n"
\t.text
\t.globl\tmain
\t.type\tmain, @function
main:
.LFB0:
\tpush\trbp
\tmov\trbp, rsp
.L2:
\tjmp\t.L2
\t.size\tmain, .-main
\t.ident\t"GCC: (Ubuntu 13.2.0) 13.2.0"
\t.section\t.note.GNU-stack,"",@progbits
\t.section\t.note.gnu.property,"a"
\t.align 8
\t.long\t1f - 0f
0:
\t.string\t"GNU"
1:
\t.long\t0xc0000002
"""

CLANG_ASM = """\
main:                                   # @main
# %bb.0:
\tpush\trbp
.Ltmp0:
\txor\teax, eax                        # zero
.LBB0_1:
\tret
.Lfunc_end0:
\t.addrsig
"""


def test_clean_gcc_asm():
    cleaned = clean_asm(GCC_ASM)
    assert cleaned.splitlines() == [
        ".LC0:", '    .string\t"x = %d\\n"', "main:", "    push\trbp", "    mov\trbp, rsp",
        ".L2:", "    jmp\t.L2",
    ]
    assert count_instructions(cleaned) == 3


def test_clean_clang_asm_strips_comments_and_internal_labels():
    cleaned = clean_asm(CLANG_ASM)
    assert cleaned.splitlines() == ["main:", "    push\trbp", "    xor\teax, eax", ".LBB0_1:", "    ret"]
    assert count_instructions(cleaned) == 3
