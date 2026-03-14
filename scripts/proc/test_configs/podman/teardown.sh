#!/usr/bin/env bash
PODMAN_USER="${SUDO_USER:-${USER:-siagraw}}"
sudo -u "$PODMAN_USER" -- podman rm -f osmosis-podman-app osmosis-podman-kvs 2>/dev/null || true
