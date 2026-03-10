# Lintool Experiment Workflow

## Environment

| Component | Location |
|-----------|----------|
| Mac source dir | `~/Documents/OSmosis-mac/scripts/proc/` |
| VM source dir | `/mnt/host/scripts/proc/` (read via 9p share — edits on Mac are instant) |
| VM Python env | `~/proc/pyenv/` |
| VM pypfs lib | `~/proc/pfs/lib/pypfs.cpython-312-aarch64-linux-gnu.so` |
| VM test binaries | `~/proc/test_programs/hello` etc. |
| VM SSH | `ssh -p 2222 siagraw@localhost` |

---

## One-Time VM Setup

```bash
# On Mac: start the VM
cd ~/Documents/OSmosis-mac/vm && ./start_vm.sh

# On VM (SSH in or use QEMU window):
bash ~/vm_install.sh    # installs packages, builds pfs, builds test programs
```

After this, all subsequent work is done remotely via SSH.

---

## Standard Test Run Command

```bash
# Run all working tests (on VM):
ssh -p 2222 siagraw@localhost "
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_graph_queries.py \
    tests/test_extraction.py \
    tests/test_scenarios.py -k 'processes or docker-regular or podman' \
    -v
"
```

**Expected: 32 passed** (14 graph queries + 13 extraction + 4 scenarios + 1 warning)

---

## Experiment Steps

### Step 1 — Pure Python graph query tests (no root, no VM needed)
```bash
cd ~/proc && source pyenv/bin/activate
python -m pytest tests/test_graph_queries.py -v
```
Tests hand-crafted NetworkX graphs — no `/proc` access.

---

### Step 2 — Extraction unit tests (root + pypfs)
```bash
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest tests/test_extraction.py -v
```
Tests each extractor (VMR, pagemap, status/uid, namespaces, mountinfo, cgroups,
hold edges, FILE resources, PAGE_QUOTA spaces).

---

### Step 3 — Full system model + query
```bash
# Extract all PIDs on the system:
cd /home/siagraw/proc/test_programs
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python /mnt/host/scripts/proc/proc_model.py \
    --os linux --pid 0 --csv /tmp/full_model.csv --query all
```

---

### Step 4 — Baseline scenario (two plain processes)
```bash
cd /home/siagraw/proc/test_programs
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python /mnt/host/scripts/proc/proc_model.py \
    --os linux --config 0 --csv /tmp/baseline.csv --query all
```
`run_configs[0]` = two `hello` processes. Confirms: same-UID hold edges,
shared FILE resources, shared PAGE_QUOTA (cgroup) space.

---

### Step 5 — Docker regular scenario
```bash
# Ensure Docker is running:
sudo systemctl start docker

cd /home/siagraw/proc/test_programs
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python /mnt/host/scripts/proc/proc_model.py \
    --os linux --config 8 --csv /tmp/docker.csv --query all
```
`run_configs[8]` = two Docker ubuntu containers. Confirms: no writable
file sharing; shared MO resources (same base image pages).

Or via pytest:
```bash
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    'tests/test_scenarios.py::test_docker_regular_no_writable_file_sharing[docker-regular]' \
    'tests/test_scenarios.py::test_docker_regular_shared_image_layers_as_mo[docker-regular]' -v
```

---

### Step 6 — Podman scenario
```bash
cd /home/siagraw/proc/test_programs
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python /mnt/host/scripts/proc/proc_model.py \
    --os linux --config 10 --csv /tmp/podman.csv --query all
```
`run_configs[10]` = two Podman ubuntu containers.

---

### Step 7 — Apptainer scenario (requires apptainer installed)
```bash
sudo snap install apptainer --classic   # one-time install

cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k apptainer -v
```
Expected: Apptainer silently shares home dir → FILE resources shared;
same parent cgroup → PAGE_QUOTA shared.

---

### Step 8 — Kata Containers scenario (requires kata runtime)
```bash
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k kata -v
```

---

### Step 9 — Docker rootless scenario (requires rootless Docker)
```bash
# Setup rootless Docker first:
dockerd-rootless-setuptool.sh install

cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k docker-rootless -v
```

---

## proc_model.py Flags Reference

| Flag | Description |
|------|-------------|
| `--pid 0` | Extract all running processes |
| `--pid N` | Extract one specific PID |
| `--pids N,M,...` | Extract multiple specific PIDs into one model |
| `--config N` | Use `run_configs[N]` to start/extract/kill (see table below) |
| `--query Q` | Run graph queries after extraction (`all`, `hold-edges`, `shared-files`, `shared-cgroups`, `shared-vmr`, `can-control`) |
| `--csv PATH` | Output CSV path |
| `--os linux` | Required for Linux extraction |

**run_configs index:**

| Index | Description |
|-------|-------------|
| 0 | Two `hello` processes |
| 2 | Two `hello_mmap` (shared memory) processes |
| 3 | Two `hello_static` processes (different binaries) |
| 8 | Two Docker ubuntu containers |
| 10 | Two Podman ubuntu containers |

---

## Results Location

- CSV and query output: `/tmp/*.csv` on VM
- Copy to Mac (via shared dir): `cp /tmp/result.csv /mnt/host/scripts/proc/outputs/`

---

## Sync Workflow

Changes on the Mac are visible immediately on the VM via the 9p share at `/mnt/host`.
The VM runs `proc_model.py` and tests directly from `/mnt/host/scripts/proc/`.
No rsync needed.

The only VM-local artifacts:
- Python venv: `~/proc/pyenv/`
- Compiled pypfs: `~/proc/pfs/lib/`
- Compiled test programs: `~/proc/test_programs/hello*`
