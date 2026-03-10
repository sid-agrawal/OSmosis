# Lintool Experiment Workflow

## Environment

| Component | Location |
|-----------|----------|
| Mac source dir | `~/Documents/OSmosis-mac/scripts/proc/` |
| VM source dir | `~/proc/` (synced from Mac via rsync or shared dir) |
| Shared dir (VM) | `/mnt/host` → Mac `~/Documents/OSmosis-mac/` |
| VM SSH | `ssh -p 2222 siagraw@localhost` |
| VM Python env | `~/proc/pyenv/` (activate: `source ~/proc/pyenv/bin/activate`) |

---

## One-Time Setup (run on VM console)

```bash
# 1. Enable passwordless sudo (needed for /proc/pagemap access in tests)
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/nopasswd

# 2. Mount shared directory (Mac -> VM)
sudo mkdir -p /mnt/host
sudo mount -t 9p -o trans=virtio,version=9p2000.L host0 /mnt/host
# Make it persist across reboots:
echo 'host0 /mnt/host 9p trans=virtio,version=9p2000.L 0 0' | sudo tee -a /etc/fstab

# 3. Install all dependencies
bash ~/vm_install.sh

# 4. Verify install
cd ~/proc && source pyenv/bin/activate
python -m pytest tests/test_graph_queries.py -v
```

---

## Sync Workflow (Mac → VM)

Sync source changes from Mac to VM:
```bash
rsync -avz -e "ssh -p 2222" \
  ~/Documents/OSmosis-mac/scripts/proc/ \
  siagraw@localhost:~/proc/ \
  --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='pyenv' --exclude='pfs/build'
```

Or just work directly on `/mnt/host/scripts/proc/` inside the VM — same files.

---

## Experiment Steps

### Step 1 — Pure Python query tests (no root needed)
```bash
cd ~/proc && source pyenv/bin/activate
python -m pytest tests/test_graph_queries.py -v
```
**Expected**: All ~15 graph query tests pass. No /proc access.

---

### Step 2 — Extraction unit tests (needs root)
```bash
cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_extraction.py -v
```
**Checks**:
- VMR list has heap, stack, vdso entries
- Static binary has no .so entries
- uid_effective matches current user
- PID and MNT namespace handles are non-zero
- mountinfo has >5 entries
- cgroup_path is non-empty and starts with `/`
- Inter-PD HOLD edges exist between same-uid processes
- FILE resource nodes exist in graph
- PAGE_QUOTA resource spaces exist in graph

---

### Step 3 — Full system model extraction
```bash
cd ~/proc && sudo pyenv/bin/python proc_model.py --os linux --pid 0 --csv /tmp/full_model.csv
python -c "
from metrics import read_csv_to_graph
from graph_queries import get_pds, get_resources, get_resource_spaces
G = read_csv_to_graph('/tmp/full_model.csv')
print(f'Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}')
print(f'PDs: {len(get_pds(G))}')
print(f'FILE resources: {len(get_resources(G, \"FILE\"))}')
print(f'PAGE_QUOTA spaces: {len(get_resource_spaces(G, \"PAGE_QUOTA\"))}')
"
```
Copy results to shared dir:
```bash
cp /tmp/full_model.csv /mnt/host/scripts/proc/outputs/full_model_$(date +%Y%m%d).csv
```

---

### Step 4 — Baseline scenario (two plain processes)
```bash
cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_scenarios.py -k processes -v
```
**Expected**:
- Same-uid processes hold each other (SIGKILL edges)
- Shared FILE resources (both see same mountpoints)
- Shared PAGE_QUOTA space (same parent cgroup)

---

### Step 5 — Docker scenario (regular + rootless)
```bash
# Ensure docker is running:
sudo systemctl start docker

# Run container tests:
cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_scenarios.py -k docker -v
```

---

### Step 6 — Podman scenario
```bash
cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_scenarios.py -k podman -v
```

---

### Step 7 — Apptainer scenario
```bash
# Install apptainer first if needed:
sudo apt-get install -y apptainer 2>/dev/null || \
  sudo snap install apptainer --classic

cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_scenarios.py -k apptainer -v
```

---

### Step 8 — Discovery / insight tests
```bash
cd ~/proc && sudo pyenv/bin/python -m pytest tests/test_analysis.py -v
```
**Key insights to confirm**:
1. Apptainer silently shares home dir → FILE resources shared
2. Docker provides stronger file isolation → FILE resources NOT shared
3. Rootless Docker: one shared slirp4netns provider
4. Podman: per-container slirp4netns
5. Apptainer: no cgroup isolation; Docker: per-container cgroup

---

## Full Test Run (all steps)
```bash
cd ~/proc && sudo pyenv/bin/python -m pytest tests/ -v \
  --tb=short \
  --ignore=tests/test_scenarios.py \   # remove to include container tests
  2>&1 | tee /mnt/host/scripts/proc/outputs/test_results_$(date +%Y%m%d).log
```

---

## Results Location

All output CSVs and test logs go to:
- VM: `/tmp/` or `/mnt/host/scripts/proc/outputs/`
- Mac (auto-synced via share): `~/Documents/OSmosis-mac/scripts/proc/outputs/`
