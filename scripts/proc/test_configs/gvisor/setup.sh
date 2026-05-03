#!/usr/bin/env bash
# setup.sh — Two gVisor containers via Docker --runtime=runsc.
# Each container runs in a separate gVisor Sentry (user-space kernel process).
# From the host, each container is visible as a runsc-sandbox process.
set -euo pipefail
export DOCKER_HOST=unix:///var/run/docker.sock

# Check gVisor runtime is configured in Docker
if ! sudo docker info --format '{{range $k,$v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null | grep -qw runsc; then
    echo "SKIP=runsc runtime not configured in Docker" >&2
    exit 1
fi

sudo docker rm -f osmosis-gvisor-app osmosis-gvisor-kvs 2>/dev/null || true
sudo docker run -d --runtime=runsc --name osmosis-gvisor-app ubuntu:22.04 sleep 3600
sudo docker run -d --runtime=runsc --name osmosis-gvisor-kvs ubuntu:22.04 sleep 3600
sleep 3

APP_PID=$(sudo docker inspect --format '{{.State.Pid}}' osmosis-gvisor-app)
KVS_PID=$(sudo docker inspect --format '{{.State.Pid}}' osmosis-gvisor-kvs)
echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
