# §7.1 matched VM-boot phase results (guest = Linux 5.18.0, buildroot 2022.08-rc2)

All runs: `qemu-system-aarch64` on the thinkpad (x86), aarch64 emulated (TCG), EL2 emulated
(`-machine virt,virtualization=on`). Same guest image (`linux` + `linux.dtb` + `rootfs.cpio.gz`) on all.

Phase markers (wall-clock ms, direct kernel boot):
p0 power-on (VMM begins) -> p1 first guest instr ("Booting Linux") -> p3 first userspace ("Run /init")
-> p4 login prompt. p1==p2 (direct boot, no firmware).

## VM boot to login (ms)

| VMM                              | p0->p1 (setup) | ->userspace | ->login | notes |
|----------------------------------|----------------|-------------|---------|-------|
| seL4 baseline VMM (GPIVM002)     | 208            | 1744        | 5493    | untracked; boots Linux OK |
| CellulOS osm-vmm  (GPIVM004)     | n/a            | n/a         | n/a     | HALTS after guest-CPU start; Linux never boots |
| Linux+KVM on emul-EL2 (config C) | 5465 (N=5)     | 63295       | 72988   | KVM heavily stresses emulated EL2 |

## Process creation (fork+exec)

| System                    | value            | notes |
|---------------------------|------------------|-------|
| Linux-in-a-VM (L1, N=300) | 27.15 ms mean / 25.61 ms median | Debian arm64 guest under qemu-TCG EL2 |
| CellulOS (existing)       | 41.6M/48.7M cyc  | hello process, seL4 PMU (from thesis) |

## Caveats
- Emulated EL2: KVM's virt-extension use is expensive to TCG-emulate, inflating Linux+KVM ~13x vs
  seL4's light VMM. Wall-clock VMM-to-VMM boot comparison is therefore NOT a real-hardware efficiency
  measure. seL4-baseline (5.5 s) is the meaningful "same guest, same emulated platform" reference.
- CellulOS's tracked VMM (osm-vmm) does not boot the Linux guest (only the minimal hello guest works).
- Unit mismatch (seL4 CCNT cycles vs wall-clock) unchanged; Odroid-C4 HW validation still future work.

## UPDATE (2026-07-08): GPIVM004 fixed — tracked-vs-untracked full Linux boot

After fixing the cellulos build (musl vis.h protected-symbol) and the test's wait loop
(block on endpoint, not sel4test_sleep/HW-timer), GPIVM004 (tracked osm-vmm) boots the 5.18
guest to login. Both from the SAME cellulos build, N=3 means (ms), same guest, emulated EL2:

| Phase       | seL4 baseline (GPIVM002, untracked) | CellulOS (GPIVM004, tracked) |
|-------------|-------------------------------------|------------------------------|
| p1 VMM setup| 242                                 | 246                          |
| p3 userspace| 2092                                | 1939                         |
| p4 login    | 6092 (6.1s)                         | 6467 (6.5s)                  |

Model-tracking overhead on full boot ~6% (amortized; setup dominated by 35MB kernel memcpy,
overhead concentrated in fault-heavy userspace phase). Cf. 20.7% on minimal hello-guest create.
High run-to-run variance (untracked login 5.65-6.36s). Emulated-EL2 caveat still applies to the
Linux+KVM (73s) cross-comparison.
