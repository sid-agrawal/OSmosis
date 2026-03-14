#!/usr/bin/env bash
# setup.sh — Podman: two ubuntu bash containers.
# Uses run_configs[10] in proc_model.py.
if ! command -v podman &>/dev/null; then
    echo "SKIP=podman not installed" >&2
    exit 1
fi
echo "CONFIG=10"
