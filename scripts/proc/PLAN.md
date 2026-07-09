# Kappa / Lintool: Research Plan

## Goal

Paper "Comparing Isolation Mechanisms with Kappa" — targeting OSDI 2027.
Previously rejected at SOSP 2025 and EuroSys 2026.

**Active paper**: `~/Documents/osmosis_papers/eurosys-2026-osmosis-compare/` (`lintool` branch).
**Code**: `~/OSmosis/scripts/proc/` (`lintool` branch).

**Invariant**: `tests/test_scenarios.py` is the truth table. Every claim in `evaluation.tex` must have a passing test. Every passing test that produces a novel finding should appear in the paper.

---

## One-Time Setup Still Needed

- [ ] Install Apptainer: `sudo snap install apptainer --classic` — unblocks 4 tests
- [ ] Update paper hardware section (`evaluation.tex` lines 53–61): i7-10850H, 6C/12T, 32GB, kernel v6.17.0-19-generic
- [ ] Fix 2 skipping docker tests: add `dockerd` PID to `test_configs/docker-regular/` and `test_configs/docker-rootless/` setup scripts

---

## Daily Loop Patterns

**Pattern A — New paper claim → test first**
1. Add the claim to `evaluation.tex` (as `\textcolor{blue}{...}` while drafting)
2. Write a test in `test_scenarios.py` asserting it
3. Run the test — if it fails, the claim is wrong or the code needs fixing
4. Commit both repos

**Pattern B — New extraction feature → update paper**
1. Implement in `proc_model.py` / `generic_model.py` / `graph_queries.py`
2. Write a test asserting the behavior
3. Update `implementation.tex` or `tab_lintool_model_linux.tex`
4. Commit both repos

**Pattern C — Re-run all experiments**
1. Run full test suite
2. For perf numbers: run `--pid 0`, capture timing, update `evaluation.tex` §6.4
3. Commit outputs to `outputs/thinkpad/`

**Pattern D — Evaluate a new isolation mechanism**
1. **Triage**: Does it use a new Linux primitive? Is it in real-world use? Can Lintool model it without new extraction code?
2. Add `test_configs/<mechanism>/setup.sh` and a test in `test_scenarios.py`
3. Run `isolation_layers()` — compare its row against the existing table
4. **Only add to paper** if the row differs from all existing rows in at least one dimension; otherwise note it in the test as `# confirms <existing mechanism>`
5. Commit both repos

---

## New Mechanism Candidates

Ranked by novelty of the `isolation_layers()` row vs. install effort.

| Mechanism | Novel dimension | Effort | Status |
|-----------|----------------|--------|--------|
| **Firecracker** | VM boundary without containerd; closes hypervisor gap from future_work | medium | not started |
| **gVisor (`runsc`)** | syscall surface is gVisor's own, not Linux's — unique row | medium | not started |
| systemd-nspawn | no daemon, no OCI, raw namespaces | low | not started |
| LXD | full-system container, different AppArmor label | low | not started |
| bubblewrap | rootless, no daemon, minimal | low | not started |
| Docker + custom seccomp | varies `syscall_surface` dimension only | low | not started |
| Podman rootful | comparison point for rootless row | low | not started |
| nsjail | namespace + seccomp from config file | medium | not started |

**Primary targets for OSDI**: Firecracker and gVisor. Both are mentioned/implied by reviewers and would add rows to Tab. 2 that no current mechanism provides.

---

## Paper ↔ Code Mapping

| Test | Paper location |
|------|---------------|
| `test_processes_baseline` | §6.2.1 hold-edges, same-UID |
| `test_docker_regular_*` | §6.2.1 Docker regular figures |
| `test_docker_rootless_*` | §6.2.1 Docker rootless figures |
| `test_podman_*` | §6.2.1 Podman figures |
| `test_apptainer_*` | §6.2.1 Apptainer figures |
| `test_kata_*` | Tab. 2 (`isolation_layers`) |
| `test_docker_daemons_h*` | Tab. 2 + §6.2.1 |
| `test_isolation_layers_*` | Tab. 2 |
| `test_fuse_*` | §6.3 FUSE finding |
| `test_grpc_*` | not yet in paper — candidate for §6.3 |
| `test_vdso_*` | §6.3 vDSO finding |

---

## Key Files

| File | Role |
|------|------|
| `evaluation.tex` (eurosys paper) | Paper claims — §6.2 scenarios, §6.3 insights, §6.4 perf, lines 53–61 hardware |
| `implementation.tex` | How features are modeled; seccomp/AppArmor limitations documented |
| `tab_lintool_model_linux.tex` | Feature table |
| `future_work.tex` | Known gaps (custom BPF extraction, MAC path rules, SELinux, hypervisors) |
| `tests/test_scenarios.py` | One test per paper claim |
| `test_configs/*/setup.sh` | Per-scenario setup |
| `outputs/thinkpad/` | Committed experiment results |
