#!/usr/bin/env bash
docker rm -f grpc-server grpc-client 2>/dev/null || true
docker network rm grpc-net 2>/dev/null || true
