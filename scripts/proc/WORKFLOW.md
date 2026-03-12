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
# Run all tests (on VM):
ssh -p 2222 siagraw@localhost "
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest tests/ -v
"
```

**Expected: 38 passed, 6 skipped** (apptainer + kata not installed → skipped)
Pre-existing failures/errors: docker-rootless (daemon not running), test_vdso_in_static_binary, test_podman_per_container_slirp.

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
hold edges, FILE resources, PAGE_QUOTA spaces, NET namespace spaces).

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
shared FILE resources, shared PAGE_QUOTA (cgroup) space, shared NET namespace space.

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
file sharing; shared MO resources (same base image pages); separate NET spaces.

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

### Step 7 — gRPC inter-container communication (requires Docker)
```bash
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k grpc -v
```
Expected: TCP connection detected → REQUEST edge from client PD to server PD;
containers in separate NET namespaces → no shared NET resource space.

Or manually:
```bash
# Run setup (builds osmosis-grpc image, starts grpc-server + grpc-client containers)
bash /mnt/host/scripts/proc/test_configs/grpc-docker/setup.sh

# Then extract and query:
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python /mnt/host/scripts/proc/proc_model.py \
    --os linux --pids <APP_PID>,<KVS_PID> --csv /tmp/grpc.csv --query service-deps
```

---

### Step 8 — Apptainer scenario (requires apptainer installed)
```bash
sudo snap install apptainer --classic   # one-time install

cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k apptainer -v
```
Expected: Apptainer silently shares home dir → FILE resources shared;
same parent cgroup → PAGE_QUOTA shared.

`run_configs[11]` = two Apptainer instances (`/tmp/ubuntu22.sif`).
setup.sh pulls the SIF if missing, then outputs `CONFIG=11`.

---

### Step 9 — Kata Containers (no-KVM / TCG mode)
```bash
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k kata-no-kvm -v
```
`run_configs[13]` = two Kata ubuntu containers with `--runtime=io.containerd.kata.v2`.
Skip condition: `containerd-shim-kata-v2` not found in PATH (no `/dev/kvm` required).

**What this tests (kata-no-kvm finding):** Without KVM, Kata runs containers inside QEMU-TCG VMs.
From the host, each container is visible only as a QEMU process in the host MNT namespace.
The in-VM isolation is opaque to host procfs. Both QEMU processes share host FILE resources.
This is a modeling limitation — kata's isolation operates below the host's observable namespace level.

**One-time VM setup** (already done on lintool VM):
- kata-static-3.27.0-arm64 extracted to `/opt/kata/`
- Wrapper at `/usr/local/bin/containerd-shim-kata-v2` filters `-root` flag (containerd 1.7 compat)
- Wrapper at `/opt/kata/bin/qemu-system-aarch64` replaces `-cpu host` → `-cpu max` and `gic-version=host` → `gic-version=3` for TCG mode
- `/dev/kvm` fake node created (major 10, minor 232) for cgroup device check
- `/etc/kata-containers/configuration.toml`: `machine_accelerators="accel=tcg"`, `sandbox_cgroup_only=true`, timeouts extended
- Containerd config at line 142 registers the kata runtime handler

---

### Step 9b — Kata Containers with KVM (x86 baremetal — TODO)

```bash
# Requires: x86 baremetal Linux with kata-containers properly installed
cd /mnt/host/scripts/proc
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k kata-kvm -v
```

Expected: same host-visible behavior as kata-no-kvm (QEMU shares host FS)
but with KVM acceleration confirmed (no `accel=tcg` in QEMU cmdline).

Skip condition: `/dev/kvm` not present (skips on ARM VM / Apple HVF hosts).

TODO: run on x86 baremetal machine when available.

---

### Step 9c — Kata vm_model (host + guest state extraction)

```bash
# On VM (kata-no-kvm available):
cd /mnt/host/scripts/proc

# Start a kata container
docker run -d --rm --runtime=io.containerd.kata.v2 \
    --name osmosis-kata-app ubuntu:22.04 sleep 3600

# Extract host QEMU state + in-VM guest state
sudo PYTHONPATH=/home/siagraw/proc/pfs/lib \
    ~/proc/pyenv/bin/python vm_model.py \
    --vmm kata --container osmosis-kata-app

# Expected output: outputs/kata/<timestamp>/guest.csv + host.csv + g2h_file.csv
# guest.csv: processes from INSIDE the kata VM (sleep, kata-agent)
# host.csv:  QEMU process model from host /proc
# g2h_file.csv: empty (QMP translation deferred — see TODO below)

# Or via pytest (tests host-side extraction):
PYTHONPATH=/home/siagraw/proc/pfs/lib \
    sudo -E ~/proc/pyenv/bin/python -m pytest \
    tests/test_scenarios.py -k kata-vm-model -v
```

**QMP memory translation (deferred):** Kata's QEMU QMP socket is at
`/run/vc/vm/<sandbox_id>/qmp.sock`. Full GPA→HPA translation mirrors
the existing QEMU telnet approach but uses a Unix socket instead.
See `_try_kata_g2h_mapping()` in `vm_model.py` for the TODO stub.

---

### Step 10 — Docker rootless scenario (requires rootless Docker)
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
| `--query Q` | Run graph queries after extraction (`all`, `hold-edges`, `shared-files`, `shared-cgroups`, `shared-vmr`, `can-control`, `service-deps`) |
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
| 11 | Two Apptainer instances (`/tmp/ubuntu22.sif`) |
| 12 | Reserved (gRPC Docker uses APP_PID= external setup) |
| 13 | Two Kata ubuntu containers (`--runtime=io.containerd.kata.v2`) — TCG mode on no-KVM hosts |

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
