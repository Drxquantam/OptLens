"""Make compiler assembly readable: drop noise directives, keep code and data."""

from __future__ import annotations

# Directives that carry data the reader cares about (string literals, tables).
_DATA_DIRECTIVES = (
    ".string", ".ascii", ".asciz", ".byte", ".short", ".value", ".word",
    ".long", ".int", ".quad", ".zero", ".float", ".double",
)
# Compiler-internal labels that are never jump targets.
_NOISE_LABEL_PREFIXES = (".Lfunc_begin", ".Lfunc_end", ".Ltmp", ".Lcfi", ".LFB", ".LFE", ".Ldebug")


def _strip_comment(line: str) -> str:
    if '"' in line:  # don't cut string literals that contain '#'
        return line
    idx = line.find("#")
    return line[:idx].rstrip() if idx != -1 else line


_SECTION_SWITCHES = (".text", ".data", ".bss", ".section", ".previous", ".pushsection", ".popsection")


def clean_asm(asm: str) -> str:
    out: list[str] = []
    in_metadata = False  # inside .note.* / .debug_* / .comment sections
    for raw in asm.splitlines():
        line = _strip_comment(raw.rstrip())
        stripped = line.strip()
        if not stripped:
            continue
        directive = stripped.split(None, 1)[0]
        if directive in _SECTION_SWITCHES:
            name = stripped.split(None, 1)[1] if " " in stripped or "\t" in stripped else ""
            in_metadata = directive in (".section", ".pushsection") and name.lstrip().startswith(
                (".note", ".debug", ".comment", ".llvm_addrsig")
            )
            continue
        if in_metadata:
            continue
        if stripped.endswith(":") and not stripped.startswith("."):
            out.append(stripped)  # function / global label
            continue
        if stripped.endswith(":"):
            if not stripped.startswith(_NOISE_LABEL_PREFIXES):
                out.append(stripped)
            continue
        if stripped.startswith("."):
            if stripped.split(None, 1)[0] in _DATA_DIRECTIVES:
                out.append("    " + stripped)
            continue
        out.append("    " + stripped)
    return "\n".join(out)


def count_instructions(cleaned: str) -> int:
    count = 0
    for line in cleaned.splitlines():
        s = line.strip()
        if s and not s.endswith(":") and not s.startswith("."):
            count += 1
    return count
