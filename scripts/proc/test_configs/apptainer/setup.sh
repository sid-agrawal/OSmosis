#!/usr/bin/env bash
# setup.sh — Start App + KVS via Apptainer (SingularityCE/Apptainer).
# Uses the Ubuntu:22.04 SIF image; pulls if missing.

set -euo pipefail

SIF_IMAGE="${APPTAINER_SIF:-/tmp/ubuntu22.sif}"

if [ ! -f "$SIF_IMAGE" ]; then
    apptainer pull "$SIF_IMAGE" docker://ubuntu:22.04
fi

apptainer instance stop osmosis-app 2>/dev/null || true
apptainer instance stop osmosis-kvs 2>/dev/null || true

apptainer instance start "$SIF_IMAGE" osmosis-app
apptainer instance start "$SIF_IMAGE" osmosis-kvs

# Get host PIDs of the shim processes
APP_PID=$(apptainer instance list | awk '/osmosis-app/{print $3}')
KVS_PID=$(apptainer instance list | awk '/osmosis-kvs/{print $3}')

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
