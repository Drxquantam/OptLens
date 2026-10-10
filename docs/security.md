# OptLens security model

OptLens compiles and runs C code submitted by anyone who can reach the UI.
That code is treated as hostile. This document describes what protects the host.

## Trust boundaries

```
browser ──HTTP──▶ FastAPI (host, unprivileged user) ──docker CLI──▶ sandbox container (one per job)
```

* The **API process never compiles or executes user code.** It validates input,
  queues the job, and starts a fresh container with `docker run`. It only *parses*
  the JSON document the container prints, through strict Pydantic models.
* The **sandbox container** is the only place user code exists. It is created
  per job and removed afterwards (`--rm`), so nothing survives between jobs.
* The API runs on the host rather than inside Docker on purpose: running it in a
  container would require mounting the Docker socket into it (root-equivalent
  access to the host), which is worse than running the API as a normal user.

## Container hardening

Every job is started with exactly these flags (see `backend/optlens/sandbox.py`,
asserted by `tests/test_api.py::test_docker_args_are_locked_down`):

| Flag | Purpose |
|---|---|
| `--network none` | no network interface besides loopback: no exfiltration, no downloads |
| `--memory 768m --memory-swap 768m` | hard memory cap, no extra swap |
| `--cpus 2` | CPU quota |
| `--pids-limit 128` | stops fork bombs |
| `--read-only` | root filesystem is immutable |
| `--tmpfs /work:...size=96m` / `--tmpfs /tmp:...size=32m` | the only writable places, size-capped, `nosuid,nodev` |
| `--cap-drop ALL` | no Linux capabilities at all |
| `--security-opt no-new-privileges` | setuid binaries cannot gain privileges |
| `--security-opt seccomp=sandbox/seccomp.json` | syscall allowlist (see below) |
| `--user 10001:10001` | non-root user, also baked into the image |
| `--ulimit nofile=256:256`, `--ulimit core=0:0` | file-descriptor cap, no core dumps |
| no `-v`/`--volume`, no `--privileged`, no socket mounts | nothing from the host is visible |

### seccomp profile

`sandbox/seccomp.json` is Docker's default seccomp profile (a default-deny
allowlist) with **one** addition: `personality(0x40000)` (`ADDR_NO_RANDOMIZE`).
MemorySanitizer re-executes itself with ASLR disabled when the kernel's memory
layout is incompatible with its shadow mapping; Docker's default profile blocks
that call, which makes every MSan build abort. Disabling ASLR *inside* a
throwaway, network-less container does not weaken the host. Setting
`OPTLENS_SECCOMP_PROFILE=""` falls back to Docker's built-in default (MSan may
then fail to start on some kernels; the verdict reports it as missing).

## Limits inside the container

`sandbox/runner.py` adds per-process limits on top of the container's:

| Limit | Default | Hard ceiling |
|---|---|---|
| Compile wall clock (per compile) | 30 s | 45 s |
| Run wall clock (per binary) | 2 s | 5 s |
| Sanitizer run wall clock | 8 s | 15 s |
| `RLIMIT_CPU` | wall clock + 1 s | |
| `RLIMIT_FSIZE` for user programs | 1 MiB | 4 MiB |
| Captured stdout/stderr | 16 KiB per stream (rest truncated) | 64 KiB |
| Assembly | 4000 lines per build | 6000 |

Each binary runs in its own process group; on timeout the whole group gets
`SIGKILL`. The backend additionally kills (`docker rm -f`) any container that
exceeds the 180 s job limit and refuses runner output larger than 16 MiB.

## Service-level protection

* **Input caps:** source ≤ 64 KiB, stdin ≤ 16 KiB, NUL bytes rejected (HTTP 413/422).
* **Rate limiting:** a sliding window of 10 analyses per client IP per 60 s (HTTP 429
  with `Retry-After`). `X-Forwarded-For` is honoured only when the direct peer is in
  `OPTLENS_TRUSTED_PROXIES` (default: loopback only), so clients cannot spoof it.
* **Concurrency cap:** a fixed pool of 2 workers means at most 2 sandbox
  containers at once; at most 16 jobs wait in the queue, beyond that HTTP 503.

All of these are configurable through `OPTLENS_*` environment variables
(`backend/optlens/config.py`).

## Known limitations (honest list)

* **Container isolation is not a VM.** A Linux kernel exploit reachable through
  the allowed syscalls could escape. For an internet-facing deployment, run the
  sandbox under gVisor (`--runtime=runsc`) or Kata/Firecracker, on a dedicated host.
* **A job can tamper with its own result.** User code runs as the same UID as the
  runner inside the container, so it could kill the runner or overwrite its own
  binaries. That only corrupts *that* job's report; it cannot affect the host or
  other jobs. Running user binaries under a second UID would close this.
* **No authentication.** The rate limiter is per-IP and in-memory; it resets on
  restart and is not shared between API replicas.
* The API binds to `127.0.0.1` by default. Don't expose it publicly without a
  reverse proxy, TLS and the hardening above.
