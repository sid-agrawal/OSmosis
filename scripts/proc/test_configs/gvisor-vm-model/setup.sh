#!/usr/bin/env bash
# setup.sh — Starts a gVisor container for two-level vm_model extraction.
# Uses ubuntu:24.04 (glibc 2.39) so that pypfs.cpython-312 can load inside
# the sandbox (pypfs requires GLIBC_2.38+ and GLIBCXX_3.4.32+).
#
# Pre-builds osmosis-gvisor-vm-test-img with python3.12 + packages installed
# in normal Docker (no gVisor) so that apt-get works reliably. The container
# then starts from this image under runsc and _push_and_run_proc_model skips
# the apt-get install step (packages already at /tmp/py312-pkgs).
set -euo pipefail
export DOCKER_HOST=unix:///var/run/docker.sock

if ! sudo docker info --format '{{range $k,$v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null | grep -qw runsc; then
    echo "SKIP=runsc runtime not configured in Docker" >&2
    exit 1
fi

# Build the base image with python3.12 + packages if not already built.
# Building happens under the normal (runc) runtime so apt-get works.
if ! sudo docker image inspect osmosis-gvisor-vm-test-img >/dev/null 2>&1; then
    echo "[setup] Building osmosis-gvisor-vm-test-img (one-time, ~60s)..." >&2
    sudo docker build -t osmosis-gvisor-vm-test-img - <<'DOCKERFILE'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && \
    apt-get install -y -qq python3.12 python3.12-venv python3-pip && \
    python3.12 -m ensurepip --upgrade 2>/dev/null || true && \
    python3.12 -m pip install --target /tmp/py312-pkgs --break-system-packages \
        --quiet networkx psutil pexpect
DOCKERFILE
fi

sudo docker rm -f osmosis-gvisor-vm-test 2>/dev/null || true
sudo docker run -d --runtime=runsc \
    --name osmosis-gvisor-vm-test \
    osmosis-gvisor-vm-test-img sleep 7200
sleep 3

SENTRY_PID=$(sudo docker inspect --format '{{.State.Pid}}' osmosis-gvisor-vm-test)
echo "SENTRY_PID=$SENTRY_PID"
echo "CONTAINER_NAME=osmosis-gvisor-vm-test"
