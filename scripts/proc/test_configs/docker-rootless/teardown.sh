#!/usr/bin/env bash
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"
docker rm -f osmosis-rootless-app osmosis-rootless-kvs 2>/dev/null || true
