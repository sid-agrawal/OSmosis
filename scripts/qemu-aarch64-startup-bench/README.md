# qemu-aarch64 startup benchmarks (§7.1, matched Linux-as-HV)

Measures VM boot **phases** and process-creation for **Linux acting as the hypervisor**, on the
*same emulated platform* and *same guest image* that CellulOS (seL4 VMM) uses, so the two can be
compared operation-for-operation in thesis §7.1 (Table 7.1).

## Why

CellulOS's VM-creation numbers (GPIVM001/003) are taken while CellulOS itself runs under
QEMU-aarch64-TCG (Cortex-A53), booting a guest via its seL4 VMM. The old Linux reference (3.6 s) was
a *full distro boot*, and Linux was not virtualized the way CellulOS is. This harness fixes both:
Linux runs as an aarch64 Cortex-A53 guest under QEMU-TCG (nested), and we time the same four boot
phases for the same guest image.

## Guest image (identical to CellulOS's)

Copied verbatim from `projects/sel4-gpi/apps/vmm/board/qemu_arm_virt/` (`guest/`):

- **Kernel: Linux 5.18.0**, aarch64, SMP PREEMPT, built with `aarch64-none-elf-gcc 10.2.1`
  (buildroot 2022.08-rc2). `guest/linux` (uncompressed Image), `guest/linux.dtb`.
- **Initramfs**: `guest/rootfs.cpio.gz` (buildroot userland; BusyBox init + getty).
- Bootargs: `earlycon=pl011,0x9000000 console=ttyAMA0 loglevel=8`.

## Boot phases (direct kernel boot — matches CellulOS, no firmware)

- **p0** power-on = qemu launch (`clock milliseconds` before spawn).
- **p1** first guest instruction (VMM setup cost = p1-p0). Precise value via QEMU gdbstub HW
  breakpoint at the kernel entry; proxy = first serial byte / kernel banner.
- **p2** first Linux instruction — coincident with p1 under direct boot (report ≈0).
- **p3** first userspace instruction — kernel prints `Run /init as init process`.
- **p4** login prompt — BusyBox getty prints `login:`.

`boot_phases.exp` spawns qemu under a PTY (avoids qemu's block-buffering on a pipe) and emits
`PHASE:<name>:<ms-since-spawn>` for each marker. The guest kernel's own `[ N.NNNNNN]` printk
timestamps give HV-independent kernel-internal timing for p2→p3.

## Linux-as-HV execution model (matches CellulOS)

On an x86 host there is no ARM silicon, so one level of aarch64 emulation (the outer `qemu-TCG`) is
unavoidable. We avoid a *second* level and match CellulOS's mechanism as follows:

- **L1** = Debian arm64 booted by `qemu-system-aarch64 -M virt,virtualization=on,gic-version=3
  -cpu max` on the thinkpad. `virtualization=on` gives L1 an (emulated) **EL2**, so its kernel boots
  at EL2 and `/dev/kvm` appears ("All CPU(s) started at EL2", KVM GICv3 sysreg interface enabled).
- **L2** = the identical 5.18 guest, launched *inside* L1 by `qemu-system-aarch64 -M virt -cpu host
  -enable-kvm` (i.e. Linux+KVM is the VMM).

This mirrors CellulOS exactly: a single outer `qemu-TCG` emulates EL2, and the VMM (Linux+KVM here,
seL4+VMM for CellulOS) uses that EL2 to run the guest at EL1 — one emulation level for both, same
mechanism.

**Caveat (absolute speed):** because EL2/KVM world-switches and stage-2 faults are themselves
emulated by the outer TCG, KVM-on-emulated-EL2 is actually *slower* in wall-clock than plain
single-level TCG (login ~79 s vs ~4.3 s). That is expected and applies equally to CellulOS's guest
(also emulated EL2), so the *comparison* between the two VMMs on the same emulated platform is fair;
only the absolute magnitudes are inflated by emulation. This is a separate caveat from the
seL4-cycles-vs-wall-clock unit mismatch.

## Status

- [x] Guest image extracted; single-level boot validated end-to-end.
- [x] Phase-timing method validated (`boot_phases.exp`).
- [x] Nested Linux-as-HV via KVM-on-emulated-EL2 (config C) — L1 Debian arm64, L2 = identical guest.
- [x] Process creation inside L1 (Linux-in-a-VM): 27.2 ms mean.
- [x] CellulOS-side phases: GPIVM002 (seL4 baseline) boots the Linux guest to login in 5.5 s.
- [x] Finding: GPIVM004 (tracked osm-vmm) HALTS on the Linux guest (no guest output) — §7.3 limitation.
- [x] Finding: KVM-on-emulated-EL2 is ~13x slower than seL4 baseline for the same guest — an emulation
      artifact, not a HW-efficiency result. See `results/SUMMARY.md`.
- [x] Written into thesis §7.1 (`content/performance.tex`, `tab:perf_vmphases`), all orange.
- [ ] Real-hardware (Odroid-C4) validation — future work (removes the emulation confound).

### Linux-as-HV results (config C: KVM on emulated EL2, `-cpu host`, L2=5.18 guest)

VM boot phases, wall-clock ms from qemu launch, N=5 (`results/linux_hv_boot_*.csv`):

| iter | p1 guest_entry | p3 userspace | p4 login |
|---|---|---|---|
| mean (N=5) | 5465 | 63295 | 72988 |

Derived: p0→p1 (VMM setup) 5.5 s; p1→p2 ≈0 (direct boot); p2→p3 (kernel) 57.8 s;
p3→p4 (userspace→login) 9.7 s; total→login 73.0 s.

Process creation inside L1 (fork+exec, N=300, `results/linux_hv_proc_*.txt`):
mean **27.15 ms**, median **25.61 ms**, σ 4.95 ms.

### Single-level baseline (thinkpad, qemu-aarch64 TCG, cortex-a53, 512 MB), N=1

| Phase | host ms (from launch) | guest kernel clock |
|---|---|---|
| kernel banner (Linux 5.18) | ~first output | `[0.000000]` |
| first userspace (`Run /init`) | 960 | `[0.736786]` |
| login prompt (`login:`) | 4328 | — |

p2→p3 (kernel→userspace) ≈ 0.74 s; p3→p4 (userspace→login) ≈ 3.37 s (dominated by `S40network`
DHCP + crng-init). Nested (TCG-in-TCG) will scale these up by the extra emulation level — a caveat to
document alongside the existing seL4-cycles-vs-wall-clock unit mismatch.

## Files

- `guest/` — the identical 5.18 guest (kernel, dtb, initramfs, kernel config).
- `boot_phases.exp` — PTY-based boot-phase timer.
- `results/` — captured serial logs + CSVs.
