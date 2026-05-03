#!/usr/bin/env bash
# setup.sh — Start App + KVS in rootless Docker containers.
# Requires rootless Docker to be configured (dockerd-rootless-setuptool.sh).

set -euo pipefail

# Point at the rootless Docker socket.
# When run as root (via sudo), id -u returns 0, so we fall back to uid 1000 (the
# owning user). If XDG_RUNTIME_DIR is set (rootless user session), use that.
ROOTLESS_UID="${SUDO_UID:-${XDG_RUNTIME_DIR:+$(stat -c %u "${XDG_RUNTIME_DIR}")}}"
ROOTLESS_UID="${ROOTLESS_UID:-1000}"
export DOCKER_HOST="unix:///run/user/${ROOTLESS_UID}/docker.sock"

# Require rootless Docker socket to be present
if ! [ -S "${DOCKER_HOST#unix://}" ]; then
    echo "SKIP=rootless Docker socket not found at $DOCKER_HOST" >&2
    exit 1
fi

APP_NAME="osmosis-rootless-app"
KVS_NAME="osmosis-rootless-kvs"

docker rm -f "$APP_NAME" "$KVS_NAME" 2>/dev/null || true

docker run -d --name "$APP_NAME" ubuntu:22.04 sleep 3600
docker run -d --name "$KVS_NAME" ubuntu:22.04 sleep 3600

APP_PID=$(docker inspect --format '{{.State.Pid}}' "$APP_NAME")
KVS_PID=$(docker inspect --format '{{.State.Pid}}' "$KVS_NAME")

# Include rootless dockerd, rootlesskit, and slirp4netns so the model shows the full TCB.
ROOTLESS_DOCKERD_PID=$(pgrep -u "$ROOTLESS_UID" -x dockerd | head -1 || true)
ROOTLESSKIT_PID=$(pgrep -u "$ROOTLESS_UID" -x rootlesskit | head -1 || true)
SLIRP_PID=$(pgrep -u "$ROOTLESS_UID" -x slirp4netns | head -1 || true)
EXTRA=""
[ -n "$ROOTLESS_DOCKERD_PID" ] && EXTRA="$ROOTLESS_DOCKERD_PID"
[ -n "$ROOTLESSKIT_PID" ] && EXTRA="${EXTRA:+$EXTRA,}$ROOTLESSKIT_PID"
[ -n "$SLIRP_PID" ] && EXTRA="${EXTRA:+$EXTRA,}$SLIRP_PID"

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
[ -n "$EXTRA" ] && echo "EXTRA_PIDS=$EXTRA"
