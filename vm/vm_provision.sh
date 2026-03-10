#!/usr/bin/env bash
# vm_provision.sh — Run INSIDE the Ubuntu VM after first boot to install dependencies.
# Copy to VM and run: bash vm_provision.sh
# Or pipe via SSH: ssh -p 2222 user@localhost 'bash -s' < vm_provision.sh

set -euo pipefail

echo "=== Provisioning Ubuntu VM for OSmosis lintool tests ==="

# --- System packages ---
sudo apt-get update -qq
sudo apt-get install -y \
    build-essential gcc make cmake git \
    python3 python3-pip python3-venv \
    docker.io docker-compose-plugin \
    podman \
    linux-tools-generic \
    libcap-dev \
    9p-modules-dkms || true   # 9p for shared folder

# --- Enable Docker ---
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# --- Mount the host share (OSmosis-mac is shared as host0) ---
MOUNT_POINT="/mnt/host"
sudo mkdir -p "$MOUNT_POINT"
if ! mountpoint -q "$MOUNT_POINT"; then
    sudo mount -t 9p -o trans=virtio,version=9p2000.L host0 "$MOUNT_POINT" || \
        echo "Warning: 9p mount failed (may need to load 9p kernel module first)"
fi

# --- Python environment ---
PROC_DIR="$MOUNT_POINT/scripts/proc"
if [ -d "$PROC_DIR" ]; then
    cd "$PROC_DIR"
    python3 -m venv pyenv
    source pyenv/bin/activate
    pip install -q -r requirements.txt
    echo "Python environment set up in $PROC_DIR/pyenv"
else
    echo "Warning: $PROC_DIR not found. Mount the host share first."
fi

# --- Build pfs library ---
PFS_DIR="$PROC_DIR/pfs"
if [ -d "$PFS_DIR" ]; then
    cd "$PFS_DIR"
    cmake -B build -DCMAKE_BUILD_TYPE=Release . && cmake --build build -j4
    echo "pfs library built."
fi

# --- Build test programs ---
TEST_PROGS="$PROC_DIR/test_programs"
if [ -d "$TEST_PROGS" ]; then
    make -C "$TEST_PROGS" all
    echo "Test programs built."
fi

echo ""
echo "=== Provisioning complete ==="
echo "To run tests:"
echo "  cd $PROC_DIR"
echo "  source pyenv/bin/activate"
echo "  sudo python -m pytest tests/test_graph_queries.py -v"
echo "  sudo python -m pytest tests/test_extraction.py -v"
