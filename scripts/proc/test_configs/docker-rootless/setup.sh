#!/usr/bin/env bash
# setup.sh — Start App + KVS in rootless Docker containers.
# Requires rootless Docker to be configured (dockerd-rootless-setuptool.sh).

set -euo pipefail

# Point at the rootless Docker socket for the current user
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"

APP_NAME="osmosis-rootless-app"
KVS_NAME="osmosis-rootless-kvs"

docker rm -f "$APP_NAME" "$KVS_NAME" 2>/dev/null || true

docker run -d --name "$APP_NAME" ubuntu:22.04 sleep 3600
docker run -d --name "$KVS_NAME" ubuntu:22.04 sleep 3600

APP_PID=$(docker inspect --format '{{.State.Pid}}' "$APP_NAME")
KVS_PID=$(docker inspect --format '{{.State.Pid}}' "$KVS_NAME")

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
