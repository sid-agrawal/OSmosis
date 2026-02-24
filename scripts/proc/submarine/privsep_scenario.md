# Privilege Separation Scenario: Design & Progress

**Purpose**: Scalability case study for PLOS 2026 paper (revision item C5).
**Scenario key**: `"privsep"` in `SCENARIOS` dict.
**Status**: 🟡 In progress

---

## Motivation

OpenSSH's privilege separation (Niels Provos, 2002) is the canonical OS security pattern:
a monolithic root daemon was split so that the internet-facing component never touches
cryptographic key material. IsoSearch should rediscover this automatically from a
fully-shared G₀ — "the same structural answer that took years to manually engineer."

---

## OpenSSH Accuracy Assessment

| Resource | Our Model | Real OpenSSH | Accurate? |
|----------|-----------|--------------|-----------|
| Host private key | `FILE_1_1`, `FileType.CONFIG`, `/etc/ssh/ssh_host_rsa_key` | RSA/Ed25519 key in `/etc/ssh/` | ✓ |
| User credentials | `FILE_1_2`, `FileType.DATABASE`, `/etc/shadow` | `/etc/shadow` + PAM + `~/.ssh/authorized_keys` | ✓ (simplified) |
| Session state / IPC | `FILE_1_3`, `FileType.TEMP`, `/tmp/sshd_session` | Unix socketpair between monitor and child | ⚠️ Approximation: real IPC is a socket, not a file |
| Network socket | `FILE_1_4`, `FileType.SOCKET` | TCP file descriptor inherited from parent | ✓ |
| Audit log | `FILE_1_5`, `FileType.LOG`, `/var/log/auth.log` | syslog → `/var/log/auth.log` | ✓ |

**5-PD decomposition vs real OpenSSH**:
Real OpenSSH privsep has 2-3 processes: monitor (root), network child (unprivileged), session child (authenticated user).
Our 5-PD model extends this by splitting the monitor's responsibilities:
- `PD_auth` = separate authentication component (like PAM or a dedicated auth service)
- `PD_keystore` = separate key manager (like ssh-agent or an HSM)

This is a **generalization** of real OpenSSH, not a 1:1 model. The paper should say
"inspired by privilege separation, extended to 5 components to demonstrate scalability."

---

## Graph Design

### PDs (node IDs are numeric — name is display-only)

| Display Name | Node ID | Role |
|-------------|---------|------|
| PD_monitor | `PD_1` | Privileged root monitor |
| PD_net | `PD_2` | Network handler (internet-facing, unprivileged) |
| PD_session | `PD_3` | Authenticated session manager |
| PD_auth | `PD_4` | Authentication handler (PAM / public key verification) |
| PD_keystore | `PD_5` | Private key manager (like ssh-agent or HSM) |

### Resources

| Node ID | FileType | Path | Role |
|---------|----------|------|------|
| `FILE_1_1` | `CONFIG` | `/etc/ssh/ssh_host_rsa_key` | SSH host private key |
| `FILE_1_2` | `DATABASE` | `/etc/shadow` | User credentials |
| `FILE_1_3` | `TEMP` | `/tmp/sshd_session` | Session state (IPC approximation) |
| `FILE_1_4` | `SOCKET` | `/var/run/sshd.sock` | Network socket |
| `FILE_1_5` | `LOG` | `/var/log/auth.log` | Audit log |

### G₀ — Monolithic (Initial State)

All 5 PDs hold all 5 resources. 25 HOLD edges. RSI = 1.0 for all 10 pairs.

```
                FILE_1_1  FILE_1_2  FILE_1_3  FILE_1_4  FILE_1_5
PD_1 (monitor)   HOLD      HOLD      HOLD      HOLD      HOLD
PD_2 (net)       HOLD      HOLD      HOLD      HOLD      HOLD
PD_3 (session)   HOLD      HOLD      HOLD      HOLD      HOLD
PD_4 (auth)      HOLD      HOLD      HOLD      HOLD      HOLD
PD_5 (keystore)  HOLD      HOLD      HOLD      HOLD      HOLD
```

### Target State — Privilege Separated

```
                FILE_1_1  FILE_1_2  FILE_1_3  FILE_1_4  FILE_1_5
PD_1 (monitor)                                           HOLD
PD_2 (net)                                    HOLD
PD_3 (session)             HOLD (via REQUEST)  HOLD
PD_4 (auth)               HOLD
PD_5 (keystore)  HOLD

REQUEST edges:
PD_2 (net)      → PD_4 (auth)      (trigger authentication)
PD_2 (net)      → PD_1 (monitor)   (audit logging)
PD_3 (session)  → PD_1 (monitor)   (audit logging)
PD_4 (auth)     → PD_5 (keystore)  (key operations for auth)
```

### RSI in Target State (verification)

| Pair | PD_i resources | PD_j resources | RSI |
|------|---------------|---------------|-----|
| PD_2,PD_5 (net,keystore) | {FILE_1_4} | {FILE_1_1} | 0/2 = **0.0** ✓ |
| PD_2,PD_4 (net,auth) | {FILE_1_4} | {FILE_1_2} | 0/2 = **0.0** ✓ |
| PD_2,PD_3 (net,session) | {FILE_1_4} | {FILE_1_3} | 0/2 = **0.0** ✓ |
| PD_3,PD_5 (session,keystore) | {FILE_1_3} | {FILE_1_1} | 0/2 = **0.0** ✓ |

---

## Goals (4 total)

```python
Goal("RSI", 0.0, "minimize", "PD_2,PD_5"),  # net ↔ keystore: net never shares resources with key mgr
Goal("RSI", 0.0, "minimize", "PD_2,PD_4"),  # net ↔ auth:     net never shares resources with auth
Goal("RSI", 0.0, "minimize", "PD_2,PD_3"),  # net ↔ session:  net isolated from active sessions
Goal("RSI", 0.0, "minimize", "PD_3,PD_5"),  # session ↔ keystore: sessions don't see key material
```

---

## Constraints (7 total)

```python
# Functional: each PD must retain direct access to its own resource
Constraint("requires_resource_access", 1, "FILE_1_5", properties={"access_type": "direct"}),
Constraint("requires_resource_access", 2, "FILE_1_4", properties={"access_type": "direct"}),
Constraint("requires_resource_access", 3, "FILE_1_3", properties={"access_type": "direct"}),
Constraint("requires_resource_access", 4, "FILE_1_2", properties={"access_type": "direct"}),
Constraint("requires_resource_access", 5, "FILE_1_1", properties={"access_type": "direct"}),
# Security invariants: PD_2 (net) must never directly hold sensitive resources
Constraint("prohibit_direct_hold", 2, "FILE_1_1"),  # never hold host key
Constraint("prohibit_direct_hold", 2, "FILE_1_2"),  # never hold credentials
```

---

## Expected Search Behavior

Minimum steps to reach all 4 goals:
- Remove FILE_1_1 from PD_2 (net) → begins reducing RSI[PD_2,PD_5]
- Remove FILE_1_1, FILE_1_3, FILE_1_4, FILE_1_5 from PD_5 (keystore) → RSI[PD_2,PD_5] = 0 ✓
- Remove FILE_1_2 from PD_2 (net) → begins reducing RSI[PD_2,PD_4]
- Remove FILE_1_1, FILE_1_3, FILE_1_4, FILE_1_5 from PD_4 (auth) → RSI[PD_2,PD_4] = 0 ✓
- Remove FILE_1_1, FILE_1_2, FILE_1_5 from PD_2 (net) → begins RSI[PD_2,PD_3]
- Remove remaining from PD_3 → RSI[PD_2,PD_3] = 0 ✓
- Remove from PD_3 and PD_5 → RSI[PD_3,PD_5] = 0 ✓

This is a significantly longer path (~10-15 steps) than existing 3-step scenarios.
Demonstrates scalability of beam search over longer horizons.

---

## Connection to Paper

- **C5**: This is the scalability case study. Needs timing instrumentation in isosearch.py.
- **C4**: The search may add superfluous mediator PDs — graph size penalty should prevent this.
- **C3**: Once IB is implemented, add `Goal("IB", 1, "minimize", "PD_2")` — net's impact boundary ≤ monitor.
- **Table 1**: Will add a row for this scenario once results are collected.

---

## TODO

- [x] Graph design finalized
- [x] Goals and constraints defined
- [x] OpenSSH accuracy assessed
- [x] Implement `build_privsep_graph()` in `scenarios.py`
- [x] Add `"privsep"` to `SCENARIOS` dict
- [ ] Add timing instrumentation to `isosearch.py`
- [x] Run end-to-end search
- [x] Verify all 4 goals met (12 iterations, --max-iterations 30)
- [ ] Verify no superfluous PDs in solution (C4 size penalty needed)
- [x] Record: iterations=12, candidates evaluated=2094, discarded=2016
- [ ] Add row to paper `eval-tab.tex`
- [ ] Write case study text in `case_study.tex`

## Run Command

```bash
cd submarine
source .venv/bin/activate
python3 isosearch.py privsep --max-iterations 30 --quiet
```

## Results (latest run)

| Metric | Value |
|--------|-------|
| Iterations to first complete solution | 12 |
| Total candidates evaluated | 2,094 |
| Total candidates discarded | 2,016 (96%) |
| Complete solutions (30 iter) | 20 |
| Goals met | RSI[PD_2,PD_5]=0, RSI[PD_2,PD_4]=0, RSI[PD_2,PD_3]=0, RSI[PD_3,PD_5]=0 ✓ |
| Constraints satisfied | All 7 ✓ |

## Key Bug Fixes Applied

1. **`goal_driven_scoring.py`**: `count_constraint_violations` was using `graph.g[u][v].get('type')` which fails for `MultiDiGraph` (returns `AtlasView`, not dict). Fixed with `_has_hold_edge()` / `_has_request_edge()` helpers.
2. **`isosearch.py` `GreedyDesignSpaceExploration`**: `maxIterations` was hardcoded at 10. Added `max_iterations` parameter wired to `--max-iterations` CLI flag.
3. **`isosearch.py` `GenerateCandidate`**: Diversity filter blocked ALL same-type candidates every other iteration. Changed to only filter when the same-type best score is ≤ best-alternative + 1.0 (allows consecutive `remove_hold_edge` when clearly best).
