#!/usr/bin/env bash
# vm_install.sh — Run this INSIDE the VM (not via SSH) to install all dependencies.
# Usage: bash ~/vm_install.sh
set -euo pipefail

PROC_DIR="$HOME/proc"

echo "=== [1/5] System packages ==="
sudo apt-get update -qq
sudo apt-get install -y \
    build-essential gcc g++ make cmake git \
    python3-pip python3-venv python3-dev \
    docker.io \
    podman \
    libcap-dev pkg-config \
    linux-tools-generic \
    pybind11-dev \
    python3-pybind11

echo "=== [2/5] Docker setup ==="
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
echo "NOTE: log out and back in (or run 'newgrp docker') to use docker without sudo"

echo "=== [3/5] Python virtual environment ==="
cd "$PROC_DIR"
python3 -m venv pyenv
source pyenv/bin/activate
pip install --upgrade pip -q
pip install -q \
    networkx pandas pytest psutil \
    pexpect neo4j \
    pybind11

echo "=== [4/5] Build pfs (pypfs) library ==="
PFS_DIR="$PROC_DIR/pfs"
if [ -d "$PFS_DIR" ] && [ -f "$PFS_DIR/CMakeLists.txt" ]; then
    cd "$PFS_DIR"
    cmake -B build -DCMAKE_BUILD_TYPE=Release . 2>&1 | tail -5
    cmake --build build -j$(nproc) 2>&1 | tail -5
    # Copy the .so into pfs/lib so proc_model.py can find it
    mkdir -p "$PFS_DIR/lib"
    find "$PFS_DIR/build" -name "*.so" -exec cp {} "$PFS_DIR/lib/" \;
    echo "pypfs built: $(ls $PFS_DIR/lib/)"
else
    echo "WARNING: pfs/CMakeLists.txt not found — pypfs must be built manually"
    echo "  Expected location: $PFS_DIR"
fi

echo "=== [5/5] Build test C programs ==="
cd "$PROC_DIR/test_programs"
make all
echo "Built: $(ls $PROC_DIR/test_programs/hello*)"

echo ""
echo "=== Install complete ==="
echo "To run tests:"
echo "  cd $PROC_DIR && source pyenv/bin/activate"
echo "  sudo pyenv/bin/python -m pytest tests/test_graph_queries.py -v   # no root needed"
echo "  sudo pyenv/bin/python -m pytest tests/test_extraction.py -v      # needs root"
