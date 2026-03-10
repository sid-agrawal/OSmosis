#!/usr/bin/env bash
# install_vm.sh — Boot the Ubuntu ISO installer in QEMU.
# Complete the Ubuntu installer in the QEMU window, then shut down.
# After this, use start_vm.sh for all subsequent boots.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ISO="$SCRIPT_DIR/ubuntu-24.04.4-live-server-arm64.iso"
DISK="$SCRIPT_DIR/ubuntu.qcow2"
UEFI_CODE="/opt/homebrew/share/qemu/edk2-aarch64-code.fd"
UEFI_VARS="$SCRIPT_DIR/efi_vars.fd"

if [ ! -f "$ISO" ]; then
    echo "Error: ISO not found. Run ./setup_vm.sh first."
    exit 1
fi
if [ ! -f "$DISK" ]; then
    echo "Error: Disk not found. Run ./setup_vm.sh first."
    exit 1
fi

echo "Starting Ubuntu installer..."
echo "  - RAM: 8 GB, CPUs: 4"
echo "  - VGA output in QEMU window (or use VNC on :5900)"
echo "  - SSH port forwarded: localhost:2222 -> VM:22"
echo ""

qemu-system-aarch64 \
    -machine virt,accel=hvf \
    -cpu host \
    -smp 4 \
    -m 8192 \
    -drive if=pflash,format=raw,file="$UEFI_CODE",readonly=on \
    -drive if=pflash,format=raw,file="$UEFI_VARS" \
    -drive file="$DISK",if=virtio,format=qcow2 \
    -cdrom "$ISO" \
    -boot d \
    -device virtio-net-pci,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::2222-:22 \
    -device virtio-gpu-pci \
    -device qemu-xhci \
    -device usb-kbd \
    -device usb-tablet \
    -display cocoa \
    -serial mon:stdio
