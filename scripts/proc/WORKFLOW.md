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

## Reading the output

Lintool emits one CSV that is a node-and-edge list for the OSmosis graph of the machine at
the moment of extraction.

```
NODE_TYPE,NODE_ID,DATA,EDGE_TYPE,EDGE_FROM,EDGE_TO,EXTRA
```

A row is either a node or an edge, never both. Node rows fill the first three columns and
leave the edge columns empty; edge rows do the reverse. `EXTRA` carries a JSON blob on both.

**Node types**, with the counts from the whole-machine run described in Step 3:

| NODE_TYPE | Count | What it is |
|---|---|---|
| `PD` | 383 | A protection domain. One per process, plus the kernel as a distinguished PD. |
| `RESOURCE` | 730,441 | Anything a PD can hold: a memory object, a file, a VMR, a quota. |
| `RESOURCE_SPACE` | 568 | The space a resource is drawn from: an address space, a mount namespace, a cgroup. |

**Edge types**, the four from the model:

| EDGE_TYPE | Count | Meaning |
|---|---|---|
| `HOLD` | 895,233 | The PD can access this resource, with permissions in `DATA` (`RWX` and so on). |
| `MAP` | 933,051 | One resource is backed by another, for example a virtual page by a physical frame. |
| `SUBSET` | 730,441 | The resource is drawn from this resource-space. |
| `REQUEST` | 951 | The PD can ask another PD for a resource of some type. Inferred for syscalls to the kernel, and from live TCP connections between processes. |

A PD row carries the process attributes in `EXTRA`: effective and host uid, effective
capability mask, seccomp mode, LSM label, and the allowed syscall set. For example:

```
PD,PD_1,systemd,,,,{"uid_effective": 0, "cap_eff": "0x1ffffffffff", "seccomp": 0,
                    "lsm_label": "unconfined", "allowed_syscalls": [...]}
```

### What a skipped PID looks like

A kernel thread skipped during a whole-machine run is **still present as a PD node** with
all of the above attributes. Only its memory extraction is skipped, because it has no
address space. So `PD_2,kthreadd` appears, but holds no `MO` resources. This is why the PD
count (383) is larger than the extracted count (163): the skip is partial, not total. Do
not read a PD with no memory resources as a process that holds nothing.

### The queries

`--query all` runs every canned query over the extracted graph and prints the results. Each
can be run alone, which is the quickest way to tell whether an extraction did something
sensible before pulling the CSV into neo4j.

| Query | Answers |
|---|---|
| `hold-edges` | Which PDs can signal or terminate which others. |
| `can-control` | The TCB of each PD: everything that could kill it. |
| `shared-files` | Which pairs of PDs have a file in common. |
| `shared-cgroups` | Which pairs share a page-quota (cgroup) space. |
| `shared-vmr` | Which pairs share a memory region. |
| `service-deps` | REQUEST edges inferred from live TCP connections between PDs. |

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
