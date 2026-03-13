#!/usr/bin/env bash
set -euo pipefail
docker rm -f osmosis-docker-app osmosis-docker-kvs 2>/dev/null || true
docker run -d --rm --name osmosis-docker-app ubuntu:22.04 sleep 3600
docker run -d --rm --name osmosis-docker-kvs ubuntu:22.04 sleep 3600
sleep 1
APP_PID=$(docker inspect --format '{{.State.Pid}}' osmosis-docker-app)
KVS_PID=$(docker inspect --format '{{.State.Pid}}' osmosis-docker-kvs)
DOCKERD_PID=$(pgrep -x dockerd | head -1)
CONTAINERD_PID=$(pgrep -x containerd | head -1)
echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
echo "EXTRA_PIDS=$DOCKERD_PID,$CONTAINERD_PID"
echo "WITH_ANCESTORS=true"
