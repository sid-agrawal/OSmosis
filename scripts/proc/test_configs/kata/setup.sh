#!/usr/bin/env bash
# setup.sh — Kata Containers scenario setup.
# Requires containerd + kata-runtime configured.
# Delegates start/extract/kill to proc_model.py run_configs[13].

set -euo pipefail

# proc_model.py run_configs[13] starts two Kata containers
echo "CONFIG=13"
