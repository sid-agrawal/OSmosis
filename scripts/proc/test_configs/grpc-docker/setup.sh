#!/usr/bin/env bash
# setup.sh — Build and start gRPC server + client in separate Docker containers
# on a shared Docker bridge network.
# Outputs APP_PID (client) and KVS_PID (server) for proc_model.py --pids mode.

set -euo pipefail
# Always use the rootful Docker daemon.
export DOCKER_HOST=unix:///var/run/docker.sock

NET="grpc-net"
docker network create "$NET" 2>/dev/null || true
docker rm -f grpc-server grpc-client 2>/dev/null || true

# Build image from test_programs/grpc_example/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker build -t osmosis-grpc "$SCRIPT_DIR/../../test_programs/grpc_example/"

# Start server
docker run -d --name grpc-server --network "$NET" osmosis-grpc python server.py
sleep 2  # let server start

# Start client pointing at server hostname
docker run -d --name grpc-client --network "$NET" osmosis-grpc python client.py grpc-server
sleep 3  # let TCP connection establish

APP_PID=$(docker inspect --format '{{.State.Pid}}' grpc-client)
KVS_PID=$(docker inspect --format '{{.State.Pid}}' grpc-server)
echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
