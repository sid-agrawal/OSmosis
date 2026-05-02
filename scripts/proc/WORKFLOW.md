# Lintool Experiment Workflow

## Environment

| Component | Location |
|-----------|----------|
| Source dir | `~/OSmosis/scripts/proc/` |
| Python venv | `~/OSmosis/scripts/proc/venv/` |
| pypfs lib | `~/OSmosis/scripts/proc/pfs/lib/pypfs.cpython-312-x86_64-linux-gnu.so` |
| Test binaries | `~/OSmosis/scripts/proc/pfs/build/out/hello` etc. |
| Results | `~/OSmosis/scripts/proc/outputs/$(hostname)/` |

This is a native x86_64 Linux setup — no VM or shared mount required.

---

## One-Time Setup

```bash
cd ~/OSmosis

# 1. Populate the pfs submodule (first clone only)
git submodule update --init scripts/proc/pfs

# 2. Build pfs C++ pybind module
cd scripts/proc/pfs
cmake -B build . && cmake --build build -j$(nproc)
mkdir -p lib && ln -sf ../build/lib/pypfs.cpython-312-x86_64-linux-gnu.so lib/

# 3. Create venv and install Python dependencies
cd ~/OSmosis/scripts/proc
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 4. (Optional) Install Apptainer for the apptainer scenario
sudo snap install apptainer --classic
```

---

## Standard Test Run Command

```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python -m pytest tests/ -v
```

**Current baseline (this machine — thinkpad):**
- **59 passed, 7 skipped** (apptainer not installed → 4 skips; rootless Docker not configured → 2 skips; vdso test → 1 skip)
- All docker, podman, kata, fuse, grpc-docker, docker-with-daemons tests pass.

---

## Experiment Steps

### Step 1 — Pure Python graph query tests (no root, no container needed)
```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python -m pytest tests/test_graph_queries.py -v
```

---

### Step 2 — Extraction unit tests (root + pypfs)
```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python -m pytest tests/test_extraction.py -v
```

---

### Step 3 — Full system model + query
```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python proc_model.py \
    --os linux --pid 0 --csv outputs/$(hostname)/full_model.csv --query all
```

---

### Step 4 — Run a specific scenario
```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python -m pytest \
    tests/test_scenarios.py -k <scenario> -v
```

Available scenarios and their paper claims:

| Scenario | Paper claim |
|----------|-------------|
| `processes` | Baseline: same-UID hold-edges, shared cgroup |
| `docker-regular` | Daemon-held containers; separate cgroups/namespaces |
| `docker-rootless` | No kernel hold; slirp4netns in TCB |
| `podman` | Per-container slirp; no daemon |
| `apptainer` | Silently shares home dir; shared cgroup |
| `kata-no-kvm` | VM boundary; host sees only QEMU process |
| `kata-kvm` | Same as no-kvm but with KVM acceleration |
| `kata-vm-model` | Guest-side extraction via vm_model.py |
| `docker-with-daemons` | isolation_layers() across 7 dimensions |
| `grpc-docker` | TCP connection → REQUEST edge |
| `fuse` | FUSE server appears in client TCB |

---

## proc_model.py Flags Reference

| Flag | Description |
|------|-------------|
| `--pid 0` | Extract all running processes |
| `--pid N` | Extract one specific PID |
| `--pids N,M,...` | Extract multiple specific PIDs |
| `--config N` | Use `run_configs[N]` to start/extract/kill |
| `--query Q` | Run graph queries after extraction (`all`, `hold-edges`, `shared-files`, `shared-cgroups`, `shared-vmr`, `can-control`, `service-deps`) |
| `--csv PATH` | Output CSV path |
| `--os linux` | Required for Linux extraction |

---

## Results Location

CSVs and query output go to `outputs/$(hostname)/<scenario>/`.
Commit these alongside code changes in the OSmosis repo (`lintool` branch).
