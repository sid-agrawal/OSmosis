#!/usr/bin/env bash
# setup.sh — Regular Docker: two ubuntu containers plus rootful dockerd in TCB.
set -euo pipefail
export DOCKER_HOST=unix:///var/run/docker.sock

docker rm -f test-docker test-docker2 2>/dev/null || true
docker run -d --name test-docker  ubuntu:22.04 sleep 3600
docker run -d --name test-docker2 ubuntu:22.04 sleep 3600
sleep 1

APP_PID=$(docker inspect --format '{{.State.Pid}}' test-docker)
KVS_PID=$(docker inspect --format '{{.State.Pid}}' test-docker2)
DOCKERD_PID=$(pgrep -x dockerd -u root | head -1 || true)

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
[ -n "$DOCKERD_PID" ] && echo "EXTRA_PIDS=$DOCKERD_PID"
echo "WITH_ANCESTORS=true"
