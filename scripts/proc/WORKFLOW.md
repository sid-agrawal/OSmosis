# Lintool Experiment Workflow

## Environment

| Component | Location |
|-----------|----------|
| Source dir | `~/OSmosis/scripts/proc/` |
| Python venv | `~/OSmosis/scripts/proc/venv/` |
| pypfs lib | `~/OSmosis/scripts/proc/pfs/lib/pypfs.cpython-<ver>-x86_64-linux-gnu.so` |
| Test binaries | `~/OSmosis/scripts/proc/pfs/build/out/hello` etc. |
| Results | `~/OSmosis/scripts/proc/outputs/$(hostname)/` |

This is a native x86_64 Linux setup — no VM or shared mount required.

---

## One-Time Setup

Prerequisites on a Debian/Ubuntu host:

```bash
sudo apt install -y git cmake build-essential python3-venv python3-dev
```

**Clone the `lintool` branch.** The repository's default branch is `cellulos`, whose
`scripts/proc/` is a materially different tree (46 files differ). A plain `git clone` gets the
wrong code.

**Order matters.** The venv must be created before the pfs build, because cmake needs the
`pybind11` that `requirements.txt` installs. pybind11 is not a system package here.

```bash
# 0. Clone, on the right branch
git clone -b lintool https://github.com/sid-agrawal/OSmosis.git ~/OSmosis
cd ~/OSmosis

# 1. Populate the pfs submodule (first clone only).
#    .gitmodules records SSH URLs, so plain `git submodule update` fails without a
#    GitHub SSH key even though every submodule repo is public. Rewrite to HTTPS:
git -c url."https://github.com/".insteadOf="git@github.com:" \
    submodule update --init scripts/proc/pfs
#    With an SSH key configured, `git submodule update --init scripts/proc/pfs` is enough.

# 2. Create venv and install Python dependencies. This must come BEFORE the pfs
#    build: cmake resolves pybind11 out of this venv.
cd scripts/proc
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. Build the pfs C++ pybind module.
#    -Dpybind11_DIR points cmake at the venv copy. Without it, configure fails with
#    "Could not find a package configuration file provided by pybind11".
cd pfs
cmake -B build . -Dpybind11_DIR="$(../venv/bin/python -m pybind11 --cmakedir)"
cmake --build build -j$(nproc)
#    ln -sfr computes the link path relative to lib/. A plain `ln -s` with a glob
#    silently creates a dangling link named with a literal asterisk.
mkdir -p lib && ln -sfr build/lib/pypfs.cpython-*-x86_64-linux-gnu.so lib/
cd ..

# 4. (Optional) Install Apptainer for the apptainer scenario
sudo snap install apptainer --classic
```

Check the build before going further:

```bash
PYTHONPATH=./pfs/lib ./venv/bin/python -c "import pypfs; print('pypfs OK')"
```

Only the `scripts/proc/pfs` submodule is needed. Do not run a recursive submodule update: the
other submodules are the seL4 tree for CellulOS and are large and irrelevant here.

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

`--pid 0` walks every PID in `/proc`. Root is required to read other processes'
`/proc/PID/pagemap`.

```bash
cd ~/OSmosis/scripts/proc
mkdir -p outputs/$(hostname)
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python proc_model.py \
    --os linux --pid 0 --csv outputs/$(hostname)/full_model.csv --query all
```

Measured on a 24-core Ubuntu 24.04 laptop, October 2026:

| | |
|---|---|
| Wall clock | about 1 min 50 s |
| PIDs seen | 383 |
| Extracted | 163 |
| Skipped | 220, all kernel threads |
| CSV | 215 MB, 3,291,069 rows |

Kernel threads have no address space, so `/proc/PID/pagemap` cannot be opened for them.
They are skipped and listed in a summary at the end of the run, so the extracted set
stays auditable. Only the skip summary distinguishes "not applicable" from "went wrong";
read it rather than assuming a clean run.

### Step 3b — A single process

```bash
cd ~/OSmosis/scripts/proc
sudo -E env PATH="./venv/bin:$PATH" PYTHONPATH=./pfs/lib python proc_model.py \
    --os linux --pid 1 --csv outputs/$(hostname)/pid1.csv --query all
```

Add `--with-ancestors` to pull in the parent chain up to PID 1, or use
`--pids 1234,5678` for a specific set. A single process takes a few seconds and
produces a CSV of roughly half a megabyte.

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
