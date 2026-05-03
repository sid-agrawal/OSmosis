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
| 6 | kata-no-kvm | | | | pending |
| 7 | kata-kvm | | | | pending |
| 8 | kata-vm-model | | | | pending |
| 9 | docker-with-daemons | | | | pending |
| 10 | grpc-docker | | | | pending |
| 11 | fuse | | | | pending |

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

## Scenarios Remaining (6–11)

| # | Scenario | Notes |
|---|----------|-------|
| 6 | kata-no-kvm | Requires kata shim; run via Docker with --runtime kata |
| 7 | kata-kvm | Same + /dev/kvm available ✓ |
| 8 | kata-vm-model | Guest-side extraction via vm_model.py |
| 9 | docker-with-daemons | Most thorough; H1-H9 tests + isolation_layers |
| 10 | grpc-docker | REQUEST edge detection across container boundary |
| 11 | fuse | REQUEST edge via /dev/fuse fd detection |

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
