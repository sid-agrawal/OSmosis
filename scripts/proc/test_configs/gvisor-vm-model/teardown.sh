#!/usr/bin/env bash
set -euo pipefail
export DOCKER_HOST=unix:///var/run/docker.sock
sudo docker rm -f osmosis-gvisor-vm-test 2>/dev/null || true
