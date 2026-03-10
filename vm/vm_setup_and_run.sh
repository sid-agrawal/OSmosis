#!/usr/bin/env bash
# vm_setup_and_run.sh
# Run this DIRECTLY on the VM (not over SSH) to do one-time setup,
# then run the basic experiments.
# Usage: bash ~/vm_setup_and_run.sh

set -euo pipefail
PROC_DIR="$HOME/proc"
RESULTS_DIR="/mnt/host/scripts/proc/outputs"

echo "======================================================"
echo " STEP 0: Passwordless sudo (needed for /proc/pagemap)"
echo "======================================================"
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/nopasswd
echo "Done."

echo ""
echo "======================================================"
echo " STEP 1: Mount shared directory (Mac <-> VM)"
echo "======================================================"
sudo mkdir -p /mnt/host
if ! mountpoint -q /mnt/host; then
    sudo mount -t 9p -o trans=virtio,version=9p2000.L host0 /mnt/host && echo "Mounted /mnt/host"
    # Add to fstab for persistence
    if ! grep -q 'host0' /etc/fstab; then
        echo 'host0 /mnt/host 9p trans=virtio,version=9p2000.L 0 0' | sudo tee -a /etc/fstab
    fi
else
    echo "/mnt/host already mounted"
fi
ls /mnt/host/ | head -5

echo ""
echo "======================================================"
echo " STEP 2: Install system packages"
echo "======================================================"
sudo apt-get update -qq
sudo apt-get install -y \
    build-essential gcc g++ make cmake git \
    python3-pip python3-venv python3-dev \
    docker.io podman \
    libcap-dev pkg-config \
    pybind11-dev python3-pybind11 2>&1 | grep -E '(Setting up|already installed)' | head -20

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo ""
echo "======================================================"
echo " STEP 3: Python virtual environment"
echo "======================================================"
cd "$PROC_DIR"
python3 -m venv pyenv
source pyenv/bin/activate
pip install -q --upgrade pip
pip install -q networkx pandas pytest psutil pexpect
echo "Python packages installed."

echo ""
echo "======================================================"
echo " STEP 4: Build pfs (pypfs) library"
echo "======================================================"
PFS_DIR="$PROC_DIR/pfs"
if [ -f "$PFS_DIR/CMakeLists.txt" ]; then
    cd "$PFS_DIR"
    cmake -B build -DCMAKE_BUILD_TYPE=Release . -DPYTHON_EXECUTABLE="$(which python3)" 2>&1 | tail -3
    cmake --build build -j"$(nproc)" 2>&1 | tail -3
    mkdir -p "$PFS_DIR/lib"
    find "$PFS_DIR/build" -name "*.so" -exec cp {} "$PFS_DIR/lib/" \;
    echo "pypfs built: $(ls $PFS_DIR/lib/ 2>/dev/null || echo 'NONE - check build output')"
else
    echo "WARNING: $PFS_DIR/CMakeLists.txt not found. Skipping pypfs build."
fi

echo ""
echo "======================================================"
echo " STEP 5: Build test C programs"
echo "======================================================"
cd "$PROC_DIR/test_programs"
make all
echo "Built: $(ls hello hello_static hello_file hello_shared_mem 2>/dev/null)"

echo ""
echo "======================================================"
echo " EXPERIMENT 1: Pure Python graph query tests"
echo "======================================================"
cd "$PROC_DIR"
source pyenv/bin/activate
python -m pytest tests/test_graph_queries.py -v 2>&1 | tee /tmp/results_graph_queries.txt
echo "Results saved to /tmp/results_graph_queries.txt"

echo ""
echo "======================================================"
echo " EXPERIMENT 2: Extraction unit tests (requires root)"
echo "======================================================"
sudo "$PROC_DIR/pyenv/bin/python" -m pytest tests/test_extraction.py -v \
    2>&1 | tee /tmp/results_extraction.txt
echo "Results saved to /tmp/results_extraction.txt"

echo ""
echo "======================================================"
echo " EXPERIMENT 3: Full system model extraction"
echo "======================================================"
sudo "$PROC_DIR/pyenv/bin/python" proc_model.py \
    --os linux --pid 0 --csv /tmp/full_model.csv
"$PROC_DIR/pyenv/bin/python" - <<'EOF'
import sys; sys.path.insert(0, '.')
from metrics import read_csv_to_graph
from graph_queries import get_pds, get_resources, get_resource_spaces
G = read_csv_to_graph('/tmp/full_model.csv')
print(f"Nodes:          {G.number_of_nodes()}")
print(f"Edges:          {G.number_of_edges()}")
print(f"PDs:            {len(get_pds(G))}")
print(f"FILE resources: {len(get_resources(G, 'FILE'))}")
print(f"PAGE_QUOTA sp:  {len(get_resource_spaces(G, 'PAGE_QUOTA'))}")
print(f"VMR resources:  {len(get_resources(G, 'VMR'))}")
print(f"MO resources:   {len(get_resources(G, 'MO'))}")
EOF

echo ""
echo "======================================================"
echo " EXPERIMENT 4: Baseline scenario (two hello processes)"
echo "======================================================"
sudo "$PROC_DIR/pyenv/bin/python" -m pytest tests/test_scenarios.py -k processes -v \
    2>&1 | tee /tmp/results_baseline.txt

echo ""
echo "======================================================"
echo " Copy results to shared dir (visible on Mac)"
echo "======================================================"
mkdir -p "$RESULTS_DIR" 2>/dev/null || true
if mountpoint -q /mnt/host 2>/dev/null; then
    DATE=$(date +%Y%m%d_%H%M)
    cp /tmp/full_model.csv      "$RESULTS_DIR/full_model_${DATE}.csv"     2>/dev/null || true
    cp /tmp/results_graph_queries.txt "$RESULTS_DIR/test_graph_queries_${DATE}.txt" 2>/dev/null || true
    cp /tmp/results_extraction.txt    "$RESULTS_DIR/test_extraction_${DATE}.txt"    2>/dev/null || true
    cp /tmp/results_baseline.txt      "$RESULTS_DIR/test_baseline_${DATE}.txt"      2>/dev/null || true
    echo "Results copied to $RESULTS_DIR"
else
    echo "NOTE: /mnt/host not mounted — results only in /tmp/ on VM"
fi

echo ""
echo "======================================================"
echo " ALL DONE. Summary of results:"
echo "======================================================"
for f in /tmp/results_*.txt; do
    echo ""
    echo "--- $f ---"
    grep -E '(PASSED|FAILED|ERROR|passed|failed|error)' "$f" | tail -5
done
