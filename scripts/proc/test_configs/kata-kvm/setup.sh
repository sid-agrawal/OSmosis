#!/usr/bin/env bash
# Kata Containers with KVM acceleration — requires /dev/kvm.
# TODO: validate on x86 baremetal Linux machine.
# Delegates start/extract/kill to proc_model.py run_configs[13].

set -euo pipefail

if [ ! -e /dev/kvm ]; then
    echo "ERROR: /dev/kvm not found. This scenario requires hardware KVM." >&2
    echo "Run on a baremetal Linux machine or a VM with nested virtualization." >&2
    exit 1
fi

echo "CONFIG=13"
