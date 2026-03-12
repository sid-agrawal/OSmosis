#!/usr/bin/env bash
# setup.sh — Apptainer scenario setup.
# Pulls the ubuntu SIF if missing, then delegates start/extract/kill to proc_model.py.

set -euo pipefail

SIF_IMAGE="${APPTAINER_SIF:-/tmp/ubuntu22.sif}"

if [ ! -f "$SIF_IMAGE" ]; then
    apptainer pull "$SIF_IMAGE" docker://ubuntu:22.04
fi

# proc_model.py run_configs[11] starts two Apptainer instances using this SIF
echo "CONFIG=11"
