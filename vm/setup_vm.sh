#!/usr/bin/env bash
# setup_vm.sh — Download Ubuntu 24.04 ARM64 ISO and create a QEMU disk image.
# Run once before first boot.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ISO="$SCRIPT_DIR/ubuntu-24.04-live-server-arm64.iso"
DISK="$SCRIPT_DIR/ubuntu.qcow2"
DISK_SIZE="40G"

# --- Download ISO if not present ---
if [ ! -f "$ISO" ]; then
    echo "Downloading Ubuntu 24.04 ARM64 server ISO..."
    curl -L -o "$ISO" \
      "https://cdimage.ubuntu.com/ubuntu-server/daily-live/current/noble-live-server-arm64.iso"
    echo "Download complete: $ISO"
else
    echo "ISO already present: $ISO"
fi

# --- Create disk image if not present ---
if [ ! -f "$DISK" ]; then
    echo "Creating $DISK_SIZE qcow2 disk image..."
    qemu-img create -f qcow2 "$DISK" "$DISK_SIZE"
    echo "Disk created: $DISK"
else
    echo "Disk already exists: $DISK"
fi

# --- Create UEFI vars copy (needed for ARM64 boot) ---
UEFI_VARS="$SCRIPT_DIR/efi_vars.fd"
UEFI_CODE="/opt/homebrew/share/qemu/edk2-aarch64-code.fd"
UEFI_VARS_TEMPLATE="/opt/homebrew/share/qemu/edk2-arm-vars.fd"

if [ ! -f "$UEFI_VARS" ]; then
    if [ -f "$UEFI_VARS_TEMPLATE" ]; then
        cp "$UEFI_VARS_TEMPLATE" "$UEFI_VARS"
        echo "UEFI vars created: $UEFI_VARS"
    else
        echo "Warning: UEFI vars template not found at $UEFI_VARS_TEMPLATE"
        echo "Creating empty 64MB UEFI vars file..."
        dd if=/dev/zero of="$UEFI_VARS" bs=1m count=64 2>/dev/null
    fi
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Run ./install_vm.sh  — boot from ISO to install Ubuntu"
echo "  2. Run ./start_vm.sh    — start the installed VM"
