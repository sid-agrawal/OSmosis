#!/usr/bin/env bash
# setup.sh — Kata Containers (TCG/no-KVM) scenario setup.
# Runs Kata containers via QEMU TCG when /dev/kvm is unavailable (e.g. nested QEMU/Apple HVF).
# Requires: kata-containers installed with TCG wrappers configured.
# Delegates start/extract/kill to proc_model.py run_configs[13].

set -euo pipefail

echo "CONFIG=13"
