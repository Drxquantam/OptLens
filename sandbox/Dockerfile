# OptLens sandbox image: compilers + a tiny runner. Untrusted code only ever
# executes inside containers started from this image (see docs/security.md).
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN printf 'Acquire::Retries "5";\nAcquire::http::Pipeline-Depth "0";\n' > /etc/apt/apt.conf.d/80-retries \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      gcc libc6-dev binutils \
      clang-18 llvm-18 libclang-rt-18-dev \
      ca-certificates \
 && ln -s /usr/bin/clang-18 /usr/local/bin/clang \
 && ln -s /usr/lib/llvm-18/bin/llvm-symbolizer /usr/local/bin/llvm-symbolizer \
 && rm -rf /var/lib/apt/lists/*

# Runtime for the runner script (kept in its own layer for faster rebuilds).
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*

# Unprivileged user; the container also runs with --user 10001:10001.
RUN groupadd -g 10001 runner && useradd -u 10001 -g 10001 -M -d /work -s /usr/sbin/nologin runner

COPY runner.py /opt/optlens/runner.py
RUN chmod 0555 /opt/optlens/runner.py

USER 10001:10001
WORKDIR /work
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python3", "-I", "/opt/optlens/runner.py"]
