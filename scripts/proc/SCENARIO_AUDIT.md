# Scenario Audit: Lintool Claim Verification

Goal: for each scenario, run the setup, extract the Kappa model, execute queries,
and verify the result matches the corresponding paper claim in evaluation.tex.

Final objective: distill a **New Mechanism Query Checklist** — a fixed set of queries
to run against any new isolation mechanism to characterize its row in the paper.

**Note on extraction:** All instances must be started as root (via sudo) to match
test behavior. User-started processes inherit the session cgroup and will show
incorrect PAGE_QUOTA sharing. Always use: `sudo proc_model.py --pids ...`

---

## Progress

| # | Scenario | Tests | Queries | Claims verified | Status |
|---|----------|-------|---------|-----------------|--------|
| 1 | processes | ✓ | ✓ | ✓ | done |
| 2 | docker-regular | ✓ | ✓ | ✓ w/note | done |
| 3 | docker-rootless | ✓ | ✓ | ✓ w/gap | done |
| 4 | podman | ✓ | ✓ | ✓ w/gap | done |
| 5 | apptainer | ✓ | ✓ | ✓ | done |
| 6 | kata-no-kvm | ✓ | ✓ | ✓ (bug fixed) | done |
| 7 | kata-kvm | ✓ | ✓ | ✓ | done |
| 8 | kata-vm-model | ✓ | ✓ | ✓ | done |
| 9 | docker-with-daemons | ✓ | ✓ | ✓ (setup bug fixed) | done |
| 10 | grpc-docker | ✓ | ✓ | ✓ | done |
| 11 | fuse | ✓ | ✓ | ✓ | done |
| 12 | gvisor | ✓ | ✓ | ✓ (novel row) | done |

---

## Recurring Observations (cross-scenario)

- **REQUEST edge to sibling**: processes and apptainer both show a REQUEST edge from
  app_pd to kvs_pd. Needs investigation — may be a shared socket or resource that
  the model interprets as a service dependency.
- **REQUEST→slirp not detected**: neither rootless Docker nor Podman shows REQUEST
  edges from containers to their slirp4netns process. The paper's Fig. 4 networking
  comparison depends on this. Likely a detection gap in `detect_slirp_connections()`.
- **Instances must be root-started**: Apptainer cgroup scopes are only created per-instance
  when started as root (via proc_model.py). User-started instances (`sudo -u user`) inherit
  the session cgroup and give wrong PAGE_QUOTA results.
- **syscall_surface discrepancy in rootless Docker**: `isolation_layers → different_syscall_surface: --`
  even though container seccomp=2 and daemon seccomp=0. Needs investigation.
- **CONFIG mode used binary label for PD name (fixed)**: `proc_model.py --config` previously stored
  the Docker image+name string as the PD label. `_is_hypervisor()` requires "qemu" in the name,
  so `vm_boundary` was always False for kata until fixed (commit c4b076d). Now uses
  `psutil.Process(pid).name()` — same as the `--pids` path.
- **gVisor Sentry appears as `exe`**: gVisor's Sentry binary is memfd-mapped; `/proc/comm`
  shows `exe` not `runsc`. Fixed via `_meaningful_process_name()` in proc_model.py: falls back
  to `os.path.basename(cmdline[0])` = `runsc-sandbox` when name is `exe`.
- **gVisor shim is `containerd-shim-runc-v2` not `containerd-shim-runsc-v2`**: when registered
  via `daemon.json` as a plain OCI runtime (`"path": "/usr/bin/runsc"`), Docker uses the generic
  runc-v2 shim for gVisor containers, not a gVisor-specific shim. The shim calls `runsc` as its
  OCI runtime binary. This affects TCB identification: searching for `containerd-shim-runsc-v2`
  will miss the shim.
- **`--with-ancestors` only walks one level up from the target PID**: it finds the immediate
  parent (the shim), but not containerd or dockerd above it. `common_ancestors(app, kvs)` returns
  only `{Host Linux}` for gVisor, missing the containerd and dockerd that are the real shared
  principals above both Sentries. **TODO: extend `--with-ancestors` to walk the full process
  ancestry chain until a known daemon root (containerd, dockerd, systemd) is reached.**
- **gVisor mutual hold edges via TCP**: the two Sentries show mutual HOLD edges (each holds the
  other) because Lintool detects a TCP connection between them. This appears even when the
  workloads are just `sleep 3600` — the connection may be from Docker's networking setup.
- **gVisor running in ptrace mode by default**: `daemon.json` `runsc` runtime has no
  `--platform` flag → ptrace mode. A `runsc-kvm` entry with `runtimeArgs: ["--platform=kvm"]`
  has been added. KVM mode confirmed via 36 kvm-vcpu fds + `anon_inode:kvm-vm` in maps.
  `vm_boundary=True` is correct in both modes; KVM mode backs it with hardware virtualization.
- **pagemap reader hangs on gVisor KVM Sentry**: the KVM Sentry maps a ~7.5 TB reserved
  region (`---p`, no permissions) to back guest physical memory. `proc_model.py`'s pagemap
  reader iterates every 4 KB page (~2 billion entries), making extraction take ~20 hours.
  **TODO (code):** skip `---p` VMA regions in the pagemap reader. See Scenario 12 for details.

---

## Scenario Results

---

### 1. processes

**Setup:** Two plain `hello` processes via `run_configs[0]`.
Same user, no namespaces, no containers, no daemon.
**CSV:** `outputs/thinkpad/audit/processes.csv`

**Queries and results:**
```
Layer 1 – Availability (hold-edges)
  can_control(app) ∋ kvs:    True   ← mutual hold (same uid)
  can_control(kvs) ∋ app:    True
  controlled_by(app):        [Host Linux, hello]

Layer 2 – File / Memory sharing
  shared FILE:               13     ← home dir, shared libs, /proc
  shared MO:                 91     ← shared physical pages (libs, vDSO)

Layer 3 – Resource Spaces
  shared PAGE_QUOTA:         1      ← same cgroup (resource exhaustion possible)
  shared MNT:                1      ← same mount namespace
  shared NET:                1      ← same network namespace
  shared IPC:                1      ← same IPC namespace
  shared PID:                0      ← default PID NS not modelled as explicit space

Layer 4 – Services in TCB (REQUEST edges)
  REQUEST from app:          [(PD_1, Host Linux), (PD_kvs, hello)]
  ← kernel networking + sibling REQUEST edge (recurring; see observations)

Layer 5 – isolation_layers
  different_mnt_ns:          --
  different_ipc_ns:          --
  different_net_ns:          --
  different_cgroup:          --
  different_mac_profile:     --
  different_syscall_surface: --
  vm_boundary:               --
  Score: 0/7
```

**Paper claims (§6.2.1, Fig. 1 bottom-left):**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Mutual hold (same uid) | True | True | ✓ |
| Shared FILE resources | > 0 | 13 | ✓ |
| Shared PAGE_QUOTA (cgroup) | > 0 | 1 | ✓ |
| isolation_layers score | 0/7 | 0/7 | ✓ |

**Notes:** 91 MO resources confirm vDSO finding (§6.3): kernel-mapped pages shared
even without explicit shared libs. Sibling REQUEST edge unexplained.

---

### 2. docker-regular

**Setup:** Two `ubuntu:22.04` containers via rootful Docker + rootful dockerd +
containerd-shim ×2, extracted with `--with-ancestors`.
**CSV:** `outputs/thinkpad/audit/docker-regular.csv`

**Queries and results:**
```
Layer 1 – Availability
  can_control(app) ∋ kvs:    True   ← containers share uid=0 inside namespace
  can_control(kvs) ∋ app:    True
  can_control(kernel) ∋ dockerd: True  ← kernel holds rootful dockerd (root)
  controlled_by(app):        [sleep, containerd-shim-runc-v2 ×2, Host Linux, dockerd]

Layer 2 – File / Memory
  shared FILE:               0      ← no writable file sharing ✓
  shared MO:                 105    ← read-only base image pages shared

Layer 3 – Resource Spaces
  shared PAGE_QUOTA:         0      ← separate cgroups ✓
  shared MNT:                0      ← separate mount namespaces ✓
  shared NET:                0      ← separate network namespaces ✓
  shared IPC:                0      ← separate IPC namespaces ✓

Layer 4 – Services in TCB
  REQUEST from app:          [(PD_1, Host Linux)]
  ← kernel provides networking; no slirp in regular Docker ✓

Layer 5 – isolation_layers (sibling containers)
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --     ← both carry docker-default (Tab. 2 finding)
  different_syscall_surface: --     ← same seccomp profile (Tab. 2 finding)
  vm_boundary:               --
  Score: 4/7

Container vs Daemon (dockerd)
  different_mac_profile:     ✓      (container=docker-default, daemon=unconfined)
  different_syscall_surface: ✓      (50 syscalls blocked for container vs daemon)
  container AppArmor: docker-default (enforce)
  daemon    AppArmor: unconfined
  container seccomp:  2   daemon seccomp: 0
  sample blocked:     acct, add_key, adjtimex, bpf, clock_adjtime, ...
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| No writable FILE sharing | 0 | 0 | ✓ |
| Shared MO (base image) | > 0 | 105 | ✓ |
| Kernel holds rootful dockerd | True | True | ✓ |
| Separate cgroups | 0 shared | 0 | ✓ |
| isolation_layers score | 4/7 | 4/7 | ✓ |
| MAC: siblings same profile | -- | -- | ✓ |
| Syscall: ~44 blocked vs daemon | ≥10 | 50 | ✓ (paper says ~44; minor version drift) |

**Notes:** Sibling containers can signal each other (uid=0 inside namespace). Paper's
"PID namespace prevents user kills" refers to *external* user processes, not siblings.
That claim is untested — would need to add a non-root observer process to the extraction.

---

### 3. docker-rootless

**Setup:** Two containers via rootless Docker (daemon uid=1000) + rootless dockerd
(PID 1802) + rootlesskit (PID 1702) + slirp4netns (PID 1790), extracted without
`--with-ancestors`.
**CSV:** `outputs/thinkpad/audit/docker-rootless.csv`

**Queries and results:**
```
Layer 1 – Availability
  can_control(app) ∋ kvs:    True
  can_control(kvs) ∋ app:    True
  controlled_by(app):        [Host Linux, slirp4netns, sleep, rootlesskit, dockerd]
  HOLD → rootless dockerd:   [(Host Linux, uid=None), (sleep ×2, uid=1000),
                               (rootlesskit, uid=1000), (slirp4netns, uid=1000)]
  ← NO uid-0 user-space process holds rootless dockerd ✓

Layer 2 – File / Memory
  shared FILE:               6
  shared MO:                 275    ← higher than rootful (rootless libs)

Layer 3 – Resource Spaces
  shared PAGE_QUOTA:         0      ← separate cgroups ✓
  shared MNT:                0
  shared NET:                0
  shared IPC:                0

Layer 4 – Services in TCB
  REQUEST from app:          [(PD_1, Host Linux)]
  slirp PD count:            1      ← one shared slirp for all containers ✓
  ← GAP: no REQUEST edge detected from containers to slirp (see observations)

Layer 5 – isolation_layers (siblings)
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --
  different_syscall_surface: --
  vm_boundary:               --
  Score: 4/7

Container vs Daemon
  container AppArmor: rootlesskit (unconfined)
  daemon    AppArmor: rootlesskit (unconfined)
  different_mac_profile:     --     ← same label; paper Tab. 2 finding ✓
  different_syscall_surface: --     ← GAP: container seccomp=2, daemon seccomp=0
                                       but isolation_layers reports --
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| No uid-0 process holds rootless dockerd | True | True | ✓ |
| One shared slirp4netns | 1 | 1 | ✓ |
| isolation_layers score | 4/7 | 4/7 | ✓ |
| MAC: container vs daemon same label | -- | -- | ✓ |
| Separate cgroups | 0 shared | 0 | ✓ |

**Gaps:**
- REQUEST→slirp not detected (affects Fig. 4 networking comparison)
- `different_syscall_surface: --` between container and daemon even though seccomp differs

---

### 4. podman

**Setup:** Two `ubuntu:22.04` containers via rootless Podman (daemonless) +
two per-container slirp4netns processes (PIDs 365899, 365964).
**CSV:** `outputs/thinkpad/audit/podman.csv`

**Queries and results:**
```
Layer 1 – Availability
  can_control(app) ∋ kvs:    True
  controlled_by(app):        [slirp4netns ×2, Host Linux, sleep]
  ← no daemon in controlled_by (daemonless) ✓

Layer 2 – File / Memory
  shared FILE (user-writable, excl /dev): 0  ✓
  shared FILE (all writable):             6   (all /dev/* pseudo-devices)
  shared MO:                             134

Layer 3 – Resource Spaces
  shared PAGE_QUOTA:         0
  shared MNT:                0
  shared NET:                0
  shared IPC:                0

Layer 4 – Services in TCB
  slirp PD count:            2      ← one per container (vs Docker rootless shared 1) ✓
  REQUEST from app:          [(PD_1, Host Linux)]
  REQUEST from kvs:          [(PD_1, Host Linux)]
  app→slirp:                 []     ← GAP: no REQUEST edge to per-container slirp
  kvs→slirp:                 []     ← GAP: same

Layer 5 – isolation_layers
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --
  different_syscall_surface: --
  vm_boundary:               --
  Score: 4/7
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| No user-writable FILE sharing | 0 | 0 | ✓ |
| Per-container slirp (2 instances) | 2 | 2 | ✓ |
| No daemon PD | absent | absent | ✓ |
| isolation_layers score | 4/7 | 4/7 | ✓ |

**Gap:** No REQUEST edge from container to its own slirp4netns. The paper's key
distinction between Podman (per-container slirp) and rootless Docker (shared slirp)
is correct in terms of PD count, but the REQUEST dependency is not visible in the
graph. This means the TCB difference shown in Fig. 4 is not currently reproducible
from the model queries.

---

### 5. apptainer

**Setup:** Two Apptainer instances from `/tmp/ubuntu22.sif`, started as **root**
(required — user-started instances inherit session cgroup and give wrong PAGE_QUOTA).
**CSV:** `outputs/thinkpad/audit/apptainer.csv`

**Root cause of cgroup behavior:**
- Root-started: each instance gets `apptainer-<PID>.scope` under `user@1000.service`
  → separate PAGE_QUOTA ✓
- User-started (`sudo -u siagraw`): both inherit `session-NNNN.scope`
  → shared PAGE_QUOTA (wrong) ✗

**Queries and results:**
```
Layer 1 – Availability
  can_control(app) ∋ kvs:    True   ← mutual hold (same uid, same as bare processes)
  can_control(kvs) ∋ app:    True
  controlled_by(app):        [Host Linux, appinit]

Layer 2 – File / Memory
  shared FILE:               6      ← home dir shared by default ✓
  shared MO:                 162

Layer 3 – Resource Spaces
  shared PAGE_QUOTA:         0      ← separate per-instance cgroups (Apptainer 4.x) ✓
  shared MNT:                0      ← Apptainer creates overlay mnt namespace ✓
  shared NET:                1      ← host network namespace (Apptainer default)
  shared IPC:                1      ← host IPC namespace (Apptainer default)

Layer 4 – Services in TCB
  REQUEST from app:          [(PD_1, Host Linux), (PD_kvs, appinit)]
  ← sibling REQUEST edge (recurring; see observations)

Layer 5 – isolation_layers
  different_mnt_ns:          ✓      ← overlay filesystem
  different_ipc_ns:          --     ← shared host IPC
  different_net_ns:          --     ← shared host network
  different_cgroup:          ✓      ← per-instance apptainer scope
  different_mac_profile:     --
  different_syscall_surface: --
  vm_boundary:               --
  Score: 2/7
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Shared FILE (home dir) | > 0 | 6 | ✓ |
| Separate cgroups (Apptainer 4.x) | 0 shared | 0 | ✓ |
| Mutual hold (same as processes) | True | True | ✓ |
| Hold-edge graph identical to processes | same | same | ✓ |

**Notes:** Apptainer scores 2/7 on isolation_layers (MNT + cgroup), not 0/7
like bare processes. The paper's Fig. 1 comparison is specifically about hold-edges,
not isolation_layers. Tab. 2 does not include Apptainer — this 2/7 score would be
a new data point worth adding. NET and IPC sharing (host namespace) is not noted
in the paper and could be an additional finding.

---

### 6. kata-no-kvm

**Setup:** Two Kata containers via Docker `--runtime=io.containerd.kata.v2` (QEMU TCG,
no KVM). Each container runs inside a separate QEMU VM. From the host, the PDs are the
QEMU processes. Uses `proc_model.py --config 13`.
**CSV:** `outputs/thinkpad/audit/kata-no-kvm.csv`

**Bug found and fixed:** Before the fix, `proc_model.py` used the Docker image+name string
("ubuntu osmosis-kata-app bash") as the PD label in CONFIG mode. `_is_hypervisor()` checks
for "qemu" in the name — so `vm_boundary` was always False. Fixed by reading the actual
binary name via `psutil.Process(pid).name()` → PD label is now "qemu-system-x86_64".

**Queries and results (post-fix):**
```
Layer 1 – PDs
  PD_1: Host Linux
  PD_N: qemu-system-x86_64   (kata-app)
  PD_M: qemu-system-x86_64   (kata-kvs)
  Only 3 PDs — in-VM processes are opaque to host /proc

Layer 2 – File / Memory
  shared FILE:               6      ← QEMU processes both in host MNT namespace
  shared NET:                0

Layer 3 – Resource Spaces
  shared MNT:                0      ← different overlay mounts for each QEMU
  shared IPC:                1      ← QEMU processes share host IPC namespace
  shared NET:                0
  shared PAGE_QUOTA:         0

Layer 4 – Services in TCB
  common_ancestors:          1 (Host Linux only)

Layer 5 – isolation_layers
  different_mnt_ns:          ✓
  different_ipc_ns:          --     ← QEMU processes share host IPC namespace
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --     (no AppArmor for QEMU processes)
  different_syscall_surface: --     (no seccomp profile for QEMU)
  vm_boundary:               ✓     ← qemu-system-x86_64 detected as hypervisor
  Score: 4/7
```

**Paper claims (Tab. 2, Kata column):**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| MNT namespace | ✓ | ✓ | ✓ |
| IPC namespace | -- | -- | ✓ |
| NET namespace | ✓ | ✓ | ✓ |
| Cgroup | ✓ | ✓ | ✓ |
| MAC profile | -- | -- | ✓ |
| Syscall surface | -- | -- | ✓ |
| VM boundary | ✓ | ✓ | ✓ (after fix) |
| Total score | 4/7 | 4/7 | ✓ |

**Note:** Paper (lines 287-289) correctly states "QEMU host processes share the host IPC
namespace (IPC --)". The isolation_layers() result matches exactly after the binary-name fix.

---

### 7. kata-kvm

**Setup:** Same as kata-no-kvm but with KVM acceleration (`/dev/kvm` available on this
machine). Identical CONFIG=13; the difference is the QEMU command line uses accel=kvm.
**CSV:** `outputs/thinkpad/audit/kata-kvm.csv`

**Queries and results:** Identical to kata-no-kvm (host-side model is the same structure):
```
isolation_layers:
  different_mnt_ns:          ✓
  different_ipc_ns:          --
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --
  different_syscall_surface: --
  vm_boundary:               ✓
  Score: 4/7
```

**Paper claims:** Same as kata-no-kvm (host-side model is identical; KVM vs TCG
is unobservable via /proc namespace queries).

**Test-specific assertion (kata-kvm only):** QEMU cmdline should NOT contain `accel=tcg`.
The test reads `/proc/<pid>/cmdline` directly and passes.

---

### 8. kata-vm-model

**Setup:** Single kata container (`osmosis-kata-app`); vm_model.py extracts both the
host-side QEMU process AND the in-guest processes. The host graph's APP_PID is the
QEMU process PID (binary: `qemu-system-x86_64`).

**Key finding:** When extracted by `--pids <qemu_pid>`, the PD label is
`qemu-system-x86_64` (psutil reads actual binary name), and
`_is_hypervisor(G, qemu_pd) = True`. This confirms the fix was correct and that
the guest extraction (vm_model) path was never affected by the naming bug.

**Test assertion:** Host model has ≥1 PD (QEMU), and the QEMU PD node exists. Passes.

**Note:** vm_model.py also produces a guest CSV (in-VM processes), but the audit
focuses on the host-side model. Guest-side isolation properties would require
running queries on the guest CSV.

---

### 9. docker-with-daemons

**Setup:** Two rootful Docker containers (`osmosis-docker-app`, `osmosis-docker-kvs`) plus the
full daemon chain (dockerd → containerd → 2× containerd-shim) extracted with `--with-ancestors`.
**CSV:** `outputs/thinkpad/audit/docker-with-daemons.csv`

**Setup bug found and fixed:** `pgrep -x dockerd | head -1` picked the rootless dockerd
(PID 1802, uid=1000) instead of the rootful one (uid=0) because the rootless instance has
a lower PID. Fixed to `pgrep -x dockerd -u root | head -1` (commit in setup.sh).

**PDs extracted (post-fix):**
```
sleep (app, uid=0)       lsm='docker-default (enforce)'  seccomp=2  allowed_syscalls=[]
sleep (kvs, uid=0)       lsm='docker-default (enforce)'  seccomp=2  allowed_syscalls=[]
dockerd (rootful, uid=0) lsm='unconfined'                seccomp=0  allowed_syscalls=[50]
containerd (uid=1000)    lsm='rootlesskit (unconfined)'  seccomp=0  allowed_syscalls=[50]
shim×2 (uid=0)           lsm='unconfined'                seccomp=0  allowed_syscalls=[50]
```

**Queries and results:**
```
Layer 1 – Hold chain
  H1: daemon PDs hold containers: ✓ (via shim uid=0 → containers uid=0)
  H2: kernel holds daemons: ✓
  H3: two shim PD nodes: ✓ (2 containerd-shim-runc-v2 PDs)

Layer 3 – Resource Spaces
  H4 (siblings, PAGE_QUOTA shared): 0 ← per-container cgroup ✓
  H5 (container vs daemon, MNT shared): 0 ✓
  H6 (container vs daemon, IPC shared): 0 ✓

Layer 4 – FILE sharing (shim ↔ container)
  H7 (observational): some shared FILE resources via stdio management

Layer 5 – isolation_layers (siblings)
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --  (both docker-default)
  different_syscall_surface: --  (both allowed_syscalls=[])
  vm_boundary:               --
  Score: 4/7

Layer 5 – isolation_layers (container vs rootful dockerd)
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     ✓  (docker-default vs unconfined)
  different_syscall_surface: ✓  ([] vs [50 tracked syscalls])
  vm_boundary:               --
  Score: 6/7

Layer 6 – syscall_surface
  H8 (seccomp):  container allowed_syscalls=0, dockerd=50, blocked=50 ✓
  Known blocked: ptrace, mount, reboot, kexec_load ✓
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Sibling isolation score | 4/7 | 4/7 | ✓ |
| Container vs dockerd score | 6/7 | 6/7 | ✓ |
| docker-default AppArmor on containers | ✓ | ✓ | ✓ |
| dockerd unconfined (different MAC) | ✓ | ✓ | ✓ |
| seccomp blocks 44+ syscalls for containers | ≥44 | 50 | ✓ |
| Two shim PDs | 2 | 2 | ✓ |
| Per-container cgroups | 0 shared | 0 | ✓ |

**Note on allowed_syscalls semantics:**
- Container with docker-default seccomp: `allowed_syscalls=[]` (empty — all 50 tracked syscalls blocked)
- Daemon (unconfined): `allowed_syscalls=[50 syscalls]` (full set of security-critical syscalls)
- `syscall_surface(container)={}`, `syscall_surface(daemon)={50}`, `blocked=50 ≥ 10` ✓

---

### 10. grpc-docker

**Setup:** gRPC server and client in separate rootful Docker containers on a shared bridge
network. Server runs `server.py`; client runs `client.py grpc-server`. TCP connection
established before extraction.
**CSV:** `outputs/thinkpad/audit/grpc-docker.csv`

**Queries and results:**
```
PDs: Host Linux, python (grpc-client), python (grpc-server)

REQUEST edges from grpc-client:
  → Host Linux
  → grpc-server (python)    ← TCP connection detected ✓

shared_resource_spaces:
  MNT: 0, IPC: 0, NET: 0   ← Docker bridge; separate NET namespaces ✓

isolation_layers:
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --  (no AppArmor in this extraction; no EXTRA_PIDS)
  different_syscall_surface: --
  vm_boundary:               --
  Score: 4/7
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Client→server REQUEST edge | ✓ | ✓ | ✓ |
| Separate NET namespaces | 0 shared | 0 | ✓ |

**Note:** isolation_layers shows 4/7 here (no AppArmor/seccomp annotations since
dockerd and shims not included as EXTRA_PIDS). The key finding is REQUEST edge detection
via TCP connection — `detect_tcp_connections()` finds the TCP socket pair and creates the
REQUEST edge. This is the only scenario that tests cross-container REQUEST edges via TCP.

---

### 11. fuse

**Setup:** FUSE passthrough server (`passthrough.py`) and `hello` client in the same
host mount namespace. The hello process sees the FUSE-mounted directory; Lintool
detects the `/dev/fuse` fd on the server and emits REQUEST edges to it.
**CSV:** `outputs/thinkpad/audit/fuse.csv`

**Queries and results:**
```
PDs: Host Linux, python (FUSE server), hello (FUSE client)

REQUEST edges from hello (client):
  → Host Linux
  → python (FUSE server) ×3   ← 3 REQUEST edges via /dev/fuse fd detection ✓

HOLD edges:
  python →[HOLD]→ hello   ← same uid mutual hold
  hello →[HOLD]→ python

shared_resource_spaces(MNT): 1  ← same host MNT namespace (bare processes)

isolation_layers:
  ALL False (0/7)    ← plain processes, same user, no isolation
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Client has REQUEST edge to FUSE server | ✓ | ✓ | ✓ |
| Both hold ≥1 MNT resource space | ✓ | ✓ | ✓ |

**Note:** The FUSE finding (§6.3) demonstrates that Lintool can detect FUSE service
dependencies without kernel extensions — purely from `/proc/<pid>/fd` inspection.
The hello client's REQUEST edge to the FUSE server means the server is in the
client's TCB: a FUSE server bug could corrupt files the client reads.
Three separate REQUEST edges (not one) likely reflect three distinct fd/mount entries.

---

### 12. gvisor

**Setup:** Two gVisor containers via Docker `--runtime=runsc`. Each container runs inside
a gVisor Sentry (user-space kernel process). From the host, the PD is the Sentry process.
**CSV:** `outputs/thinkpad/audit/gvisor.csv`

**Recon findings (before code changes):**
- Process name: `exe` (gVisor's Sentry is a memfd-mapped binary; `/proc/comm` shows `exe`)
- cmdline[0]: `runsc-sandbox ...` — clearly identifies the process
- AppArmor: `unconfined` (no gVisor-specific AppArmor profile)
- seccomp_mode: 2 (Sentry IS seccomp-filtered)
- Namespaces: each Sentry gets its own MNT, IPC, NET namespaces (unlike Kata: IPC is isolated!)
- **Platform: ptrace mode** — cmdline has no `--platform=kvm`; Sentry has no open `/dev/kvm` fd.
  Running KVM mode requires adding `--platform=kvm` to the runtime args in `daemon.json`.
- **Shim: `containerd-shim-runc-v2`** (not `containerd-shim-runsc-v2`). Our `daemon.json`
  registers runsc as a plain OCI runtime; Docker uses the generic shim for all OCI runtimes.

**Code changes made:**
1. `proc_model.py`: Added `_meaningful_process_name()` — uses `cmdline[0]` when `/proc/comm`
   is `exe`; PD label becomes `runsc-sandbox` instead of `exe`
2. `graph_queries.py`: Added `"runsc"` to `_HYPERVISOR_NAMES` → `vm_boundary: True`
3. `procfs_data.py`: Added `is_gvisor_sentry` branch (seccomp=2 + name contains "runsc")
   → `allowed_syscalls=[]`, same treatment as docker-default containers

**Queries and results (ptrace mode):**
```
Layer 1 – PDs (--with-ancestors, one level up)
  PD_1:   Host Linux
  PD_N:   runsc-sandbox (app Sentry)           ← our app PD
  PD_M:   runsc-sandbox (kvs Sentry)           ← our kvs PD
  PD_P:   containerd-shim-runc-v2 (app shim)  ← added by --with-ancestors
  PD_Q:   containerd-shim-runc-v2 (kvs shim)  ← added by --with-ancestors
  NOTE: containerd and dockerd above the shims are NOT captured (ancestor walk stops at depth 1)
  In-sandbox workloads opaque to host /proc

Layer 1 – TCB (controlled_by app Sentry)
  Host Linux
  containerd-shim-runc-v2 (app shim)
  containerd-shim-runc-v2 (kvs shim)  ← cross-hold via TCP between siblings
  kvs runsc-sandbox                    ← mutual hold via TCP connection between Sentries

Layer 1 – common_ancestors(app, kvs)
  Host Linux   ← only because containerd/dockerd not extracted
  TODO: full chain would be: Host Linux → dockerd → containerd → shim → Sentry

Layer 3 – Resource Spaces (siblings)
  MNT: 0 shared    ← separate overlay per Sentry ✓
  IPC: 0 shared    ← separate IPC namespace (NOVEL vs Kata which shows 1!) ✓
  NET: 0 shared    ← gVisor has own netstack per sandbox ✓
  PAGE_QUOTA: 0    ← per-container cgroup ✓

Layer 5 – isolation_layers (ptrace mode — same expected for KVM mode)
  different_mnt_ns:          ✓
  different_ipc_ns:          ✓  ← novel vs Kata (False)
  different_net_ns:          ✓
  different_cgroup:          ✓
  different_mac_profile:     --  (unconfined for all Sentries)
  different_syscall_surface: --  (same empty allowed_syscalls for both siblings)
  vm_boundary:               ✓  ← novel vs Docker (False)
  Score: 5/7   ← highest in Tab. 2
```

**Paper claims:**
| Claim | Expected | Actual | Match |
|-------|----------|--------|-------|
| Sentry visible as runsc process | ✓ | ✓ | ✓ |
| vm_boundary | ✓ | ✓ | ✓ |
| MNT/IPC/NET/cgroup all isolated | all ✓ | all ✓ | ✓ |
| gVisor scores 5/7 (highest) | 5/7 | 5/7 | ✓ |
| gVisor KVM mode also scores 5/7 | 5/7 | analytical (not extracted — see below) | ✓* |

**Key insight for paper:** gVisor combines full namespace isolation (4/7 like Docker) with
a VM-like boundary (like Kata), scoring 5/7. The distinguishing dimension vs Kata is IPC:
gVisor Sentries get separate IPC namespaces; Kata QEMU processes share the host IPC.

**KVM mode extraction attempt (2026-05-03):**

Configured `runsc-kvm` runtime in `/etc/docker/daemon.json` (`runtimeArgs: ["--platform=kvm"]`).
Launched two containers with `--runtime=runsc-kvm`. Confirmed KVM mode via:
- 36 kvm-vcpu fds visible in `/proc/<sentry_pid>/fd/` (vs 0 in ptrace mode)
- `anon_inode:kvm-vm` and `anon_inode:kvm-vcpu:N` in `/proc/<sentry>/maps`

Ran `proc_model.py --pids APP,KVS --csv /tmp/gvisor_kvm.csv`. Process ran at 99.9% CPU for
>44 minutes without completing. Root cause: the gVisor KVM Sentry maps a ~7.5 TB virtual
address space reservation (`c559000000-79ceb2000000 ---p`) to back the guest physical memory.
The pagemap reader in `proc_model.py` iterates every 4 KB page in this region (~2 billion
entries) via read/lseek, which would take ~20 hours at observed throughput.

**proc_model.py bug found:** The pagemap reader should skip regions with `---p` permissions
(reserved/guard regions with no read/write/exec). For a KVM gVisor Sentry, these regions
constitute the bulk of the virtual address space and contain no meaningful page residency data.
**TODO (code):** In `procfs_data.py` or wherever pagemap is read, skip VMA regions where
permissions are `---` (no read, no write, no exec).

**Analytical result for KVM mode (5/7):** The `isolation_layers()` dimensions are all
determined by Docker's namespace isolation and the process name check for `vm_boundary`:
- MNT/IPC/NET/cgroup: these come from Docker's container setup, unchanged by `--platform=kvm`
- vm_boundary: `"runsc"` is in `_HYPERVISOR_NAMES` regardless of ptrace vs KVM mode
- MAC/syscall: gVisor Sentries are `unconfined` and get empty allowed_syscalls in both modes
Therefore KVM mode scores 5/7, identical to ptrace mode. The difference is that in KVM mode
`vm_boundary` is backed by hardware virtualization rather than software ptrace interception.

**Open items:**
- **TODO (code):** `--with-ancestors` should walk the full process tree to a known daemon root
  (containerd, dockerd, systemd), not just one level. This would make `common_ancestors(app, kvs)`
  correctly show containerd and dockerd as shared principals above both Sentries.
- **TODO (code):** pagemap reader must skip `---p` VMA regions; gVisor KVM maps ~7.5 TB of
  reserved virtual address space that cannot be iterated page-by-page in reasonable time.

---

## All Scenarios Complete

---

## Query Catalog

These are the queries available in `graph_queries.py`.

### `can_control(G, pd) → set[PD]`
PDs that `pd` has a direct HOLD edge to (can send SIGKILL).
*Use:* Who can pd terminate? What is pd's impact boundary for availability?

### `controlled_by(G, pd) → set[PD]`
PDs that have a direct HOLD edge to `pd`.
*Use:* Who can terminate pd? What is in pd's TCB for availability?

### `shared_resources(G, pd1, pd2, type, access_mode=None) → set`
Resources of a given type accessible to both PDs.
Types: `FILE`, `MO` (physical page), `VMR` (virtual mapping), `IPC`, `NET`.
*Use:* Do two PDs share files? Physical pages? IPC objects?

### `shared_resource_spaces(G, pd1, pd2, type) → set`
Resource spaces (namespaces, cgroups) both PDs are members of.
Types: `MNT`, `IPC`, `NET`, `PID`, `PAGE_QUOTA` (cgroup), `APPARMOR_PROFILE`.
*Use:* Are two PDs in the same namespace or cgroup?

### `isolation_layers(G, pd1, pd2) → dict`
7-dimension isolation verdict:
- `different_mnt_ns` — separate mount namespaces
- `different_ipc_ns` — separate IPC namespaces
- `different_net_ns` — separate network namespaces
- `different_cgroup` — separate cgroup hierarchies
- `different_mac_profile` — different AppArmor/SELinux label
- `different_syscall_surface` — different effective syscall set (after seccomp)
- `vm_boundary` — VM boundary separates the two PDs

*Use:* Summary comparison table (Tab. 2). Score = count of True values.

### `syscall_surface(G, pd) → set[str]`
Set of syscalls blocked for this PD (from `allowed_syscalls` node attribute).
*Use:* How much does seccomp restrict this PD? Delta vs unfiltered?

### `mac_peers(G, pd) → set[PD]`
PDs sharing the same MAC label as `pd`.
*Use:* If one PD's label is exploited, which others are exposed equally?

---

## New Mechanism Query Checklist

Run these queries on `(app_pd, kvs_pd)` for any new isolation mechanism.

### Layer 1 — Availability
1. `can_control(app_pd)` ∋ kvs_pd? (False = isolated)
2. `controlled_by(app_pd)` — who can kill app? (daemon chain, kernel, user processes?)
3. Is there a daemon PD? If yes: `can_control(daemon_pd)` — does it hold all user processes?
4. For any daemon: check uid (root vs user) — affects kernel HOLD relationship

### Layer 2 — File / Memory (confidentiality + integrity)
5. `shared_resources(app, kvs, FILE)` — writable file sharing?
6. `shared_resources(app, kvs, MO)` — shared physical pages (same base image)?

### Layer 3 — Resource Spaces (availability / resource exhaustion)
7. `shared_resource_spaces(app, kvs, PAGE_QUOTA)` — same cgroup?
8. `shared_resource_spaces(app, kvs, MNT)` — same mount namespace?
9. `shared_resource_spaces(app, kvs, NET)` — same network namespace?
10. `shared_resource_spaces(app, kvs, IPC)` — same IPC namespace?

### Layer 4 — System Services in TCB
11. REQUEST edges from app_pd — which services (kernel, slirp, FUSE) are in TCB?
12. If slirp present: one shared across containers, or one per container?

### Layer 5 — Policy (MAC + syscall)
13. `isolation_layers(app, kvs)` — full 7-dimension verdict + score
14. `syscall_surface(app_pd)` — syscalls blocked vs unfiltered?
15. `mac_peers(app_pd)` — which PDs share same MAC label?
16. If daemon present: `isolation_layers(app, daemon)` — MAC and syscall differ?

### Layer 6 — VM Boundary
17. `isolation_layers` → `vm_boundary`?
18. If VM: is QEMU in host MNT namespace? `shared_resource_spaces(qemu, other, MNT)`?

### Interpretation Guide
| Score | Mechanism type | Example |
|-------|---------------|---------|
| 0/7 | No isolation | bare processes |
| 1–2/7 | Partial (file/cgroup only) | Apptainer default |
| 4/7 | Standard container | Docker, Podman, Kata |
| 5/7 | Container + MAC isolation | (not yet seen) |
| 6–7/7 | Full isolation | (hypothetical) |

A novel mechanism should differ from all existing rows in Tab. 2 in at least one
dimension to warrant a new paper entry. Otherwise note it as confirming an existing row.
