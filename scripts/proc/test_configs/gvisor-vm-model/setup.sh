#!/usr/bin/env bash
# setup.sh — Starts a gVisor container for two-level vm_model extraction.
# Uses ubuntu:24.04 (glibc 2.39) so that pypfs.cpython-312 can load inside
# the sandbox (pypfs requires GLIBC_2.38+ and GLIBCXX_3.4.32+).
set -euo pipefail
export DOCKER_HOST=unix:///var/run/docker.sock

if ! sudo docker info --format '{{range $k,$v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null | grep -qw runsc; then
    echo "SKIP=runsc runtime not configured in Docker" >&2
    exit 1
fi

sudo docker rm -f osmosis-gvisor-vm-test 2>/dev/null || true
sudo docker run -d --runtime=runsc \
    --name osmosis-gvisor-vm-test \
    ubuntu:24.04 sleep 7200
sleep 3

SENTRY_PID=$(sudo docker inspect --format '{{.State.Pid}}' osmosis-gvisor-vm-test)
echo "SENTRY_PID=$SENTRY_PID"
echo "CONTAINER_NAME=osmosis-gvisor-vm-test"
