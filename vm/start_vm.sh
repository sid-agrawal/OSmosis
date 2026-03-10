#!/usr/bin/env bash
# start_vm.sh — Start the installed Ubuntu VM.
# SSH: ssh -p 2222 <your-username>@localhost
# Stop: send ACPI shutdown via QEMU monitor (press Ctrl-A then C, type 'system_powerdown')

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DISK="$SCRIPT_DIR/ubuntu.qcow2"
UEFI_CODE="/opt/homebrew/share/qemu/edk2-aarch64-code.fd"
UEFI_VARS="$SCRIPT_DIR/efi_vars.fd"

if [ ! -f "$DISK" ]; then
    echo "Error: Disk not found. Run ./setup_vm.sh and ./install_vm.sh first."
    exit 1
fi

# Shared folder: mount ~/Documents/OSmosis-mac inside the VM at /mnt/host
# Access from VM: mount -t 9p -o trans=virtio,version=9p2000.L host0 /mnt/host
HOST_SHARE="${HOST_SHARE:-$HOME/Documents/OSmosis-mac}"

echo "Starting Ubuntu VM..."
echo "  SSH:    ssh -p 2222 <username>@localhost"
echo "  Share:  $HOST_SHARE -> /mnt/host (inside VM)"
echo "  Stop:   Ctrl-A C  then  system_powerdown"
echo ""

qemu-system-aarch64 \
    -machine virt,accel=hvf \
    -cpu host \
    -smp 4 \
    -m 8192 \
    -drive if=pflash,format=raw,file="$UEFI_CODE",readonly=on \
    -drive if=pflash,format=raw,file="$UEFI_VARS" \
    -drive file="$DISK",if=virtio,format=qcow2 \
    -device virtio-net-pci,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::2222-:22 \
    -virtfs local,path="$HOST_SHARE",mount_tag=host0,security_model=none,id=fs0 \
    -device virtio-gpu-pci \
    -device qemu-xhci \
    -device usb-kbd \
    -device usb-tablet \
    -display cocoa \
    -serial mon:stdio
