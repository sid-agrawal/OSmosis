#!/usr/bin/env bash
# setup.sh — Start App + KVS using Kata Containers runtime via Docker.
# Requires containerd + kata-runtime configured.

set -euo pipefail

APP_NAME="osmosis-kata-app"
KVS_NAME="osmosis-kata-kvs"

docker rm -f "$APP_NAME" "$KVS_NAME" 2>/dev/null || true

docker run -d --name "$APP_NAME" \
    --runtime=io.containerd.kata.v2 \
    ubuntu:22.04 sleep 3600

docker run -d --name "$KVS_NAME" \
    --runtime=io.containerd.kata.v2 \
    ubuntu:22.04 sleep 3600

APP_PID=$(docker inspect --format '{{.State.Pid}}' "$APP_NAME")
KVS_PID=$(docker inspect --format '{{.State.Pid}}' "$KVS_NAME")

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
