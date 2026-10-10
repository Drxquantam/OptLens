"""End-to-end tests against a real sandbox container.

Skipped automatically when Docker or the sandbox image is unavailable.
Build the image first:  docker build -t optlens-sandbox:latest sandbox
"""

from __future__ import annotations

import asyncio

import pytest

from optlens.analysis import analyze
from optlens.config import Settings
from optlens.models import Verdict
from optlens.presets import load_presets
from optlens.sandbox import DockerSandbox

_settings = Settings()
_sandbox = DockerSandbox(_settings)
_docker_ok, _image_ok = _sandbox.check()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (_docker_ok and _image_ok),
                       reason="Docker or the optlens-sandbox image is not available"),
]


def run(source: str, stdin: str = ""):
    return analyze(asyncio.run(_sandbox.run(source, stdin)))


@pytest.mark.parametrize("preset", load_presets(), ids=lambda p: p.id)
def test_preset_produces_expected_verdict(preset):
    res = run(preset.source, preset.stdin)
    assert res.verdict.verdict is preset.expected_verdict, res.verdict.model_dump_json(indent=1)
    assert all(b.compile_ok for b in res.builds)
    assert all(s.compiled for s in res.sanitizers)


def test_ub_presets_are_attributed_to_the_right_sanitizer():
    by_id = {p.id: p for p in load_presets()}

    def line_of(pid: str, needle: str) -> int:
        lines = by_id[pid].source.splitlines()
        return next(i for i, text in enumerate(lines, 1) if needle in text)

    expected = {
        "signed-overflow": ("UBSan", line_of("signed-overflow", "return x + 1 > x;")),
        "uninitialized": ("MSan", line_of("uninitialized", "return value;")),
        "out-of-bounds": ("ASan", line_of("out-of-bounds", "total += table[i];")),
    }
    for pid, (sanitizer, line) in expected.items():
        res = run(by_id[pid].source)
        found = {(f.sanitizer, f.line) for f in res.verdict.evidence}
        assert (sanitizer, line) in found, (pid, found)


def test_infinite_loop_times_out():
    res = run("int main(void){ volatile int x = 1; while (x) {} return 0; }")
    assert res.verdict.verdict is Verdict.TIMEOUT
    assert all(b.status == "timeout" for b in res.builds)


def test_compile_error_is_reported():
    res = run("int main(void) { return 0 }")
    assert res.verdict.verdict is Verdict.COMPILE_ERROR
    assert any("error" in d for d in res.verdict.details)


HARDENING = r"""
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
int main(void) {
    printf("uid=%d\n", (int)getuid());
    FILE *f = fopen("/etc/optlens-test", "w");
    printf("write_etc=%s\n", f ? "yes" : "no");
    int s = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET; a.sin_port = htons(53);
    inet_pton(AF_INET, "1.1.1.1", &a.sin_addr);
    printf("network=%s\n", (s >= 0 && connect(s, (struct sockaddr *)&a, sizeof a) == 0) ? "yes" : "no");
    for (int i = 0; i < 2000; i++) printf("spam spam spam spam spam spam spam spam\n");
    return 0;
}
"""


def test_sandbox_is_unprivileged_offline_and_output_capped():
    res = run(HARDENING)
    b = res.builds[0]
    assert b.stdout.startswith("uid=10001\nwrite_etc=no\nnetwork=no\n"), b.stdout[:200]
    assert b.stdout_truncated  # 80 KB of output, capped at 16 KB
    assert len(b.stdout.encode()) <= _settings.output_cap_bytes
