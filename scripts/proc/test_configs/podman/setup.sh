#!/usr/bin/env bash
# setup.sh — Podman rootless: two ubuntu bash containers.
# Runs as siagraw (rootless) so slirp4netns/pasta is used per container.
# Outputs APP_PID and KVS_PID directly (external-PID mode).

set -euo pipefail

if ! command -v podman &>/dev/null; then
    echo "SKIP=podman not installed" >&2
    exit 1
fi

APP_NAME="osmosis-podman-app"
KVS_NAME="osmosis-podman-kvs"

# Determine the owning user for rootless podman.
# When invoked via sudo, SUDO_USER is set; otherwise use the current user.
PODMAN_USER="${SUDO_USER:-${USER:-siagraw}}"

# Run rootless podman as the target user.
run_as() { sudo -u "$PODMAN_USER" -- "$@"; }

run_as podman rm -f "$APP_NAME" "$KVS_NAME" 2>/dev/null || true

run_as podman run --rm -id --name "$APP_NAME" ubuntu bash
run_as podman run --rm -id --name "$KVS_NAME" ubuntu bash

APP_PID=$(run_as podman inspect --format '{{.State.Pid}}' "$APP_NAME")
KVS_PID=$(run_as podman inspect --format '{{.State.Pid}}' "$KVS_NAME")

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
