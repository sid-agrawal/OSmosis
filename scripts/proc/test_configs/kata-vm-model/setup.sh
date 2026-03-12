#!/usr/bin/env bash
# Starts a single kata container; vm_model.py will extract guest+host state.
set -euo pipefail
docker rm -f osmosis-kata-app 2>/dev/null || true
docker run -d --rm --runtime=io.containerd.kata.v2 \
    --name osmosis-kata-app ubuntu:22.04 sleep 3600
sleep 3  # let kata VM fully boot
APP_PID=$(docker inspect --format '{{.State.Pid}}' osmosis-kata-app)
echo "APP_PID=$APP_PID"
echo "CONTAINER_NAME=osmosis-kata-app"
