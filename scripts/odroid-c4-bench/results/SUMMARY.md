# §7.1 startup benchmarks — Odroid-C4 (real hardware), N=5

Board: Odroid-C4 (Amlogic S905X3, Cortex-A55 @ 1.2 GHz at boot, GIC-400).
Boot: u-boot 2023.07-rc6 → TFTP → `go 0x20000000`. Console 115200 8N1.
Harness: `campaign.py` (USB relay power-cycle → u-boot → TFTP → boot → serial
capture with host-side timestamps). All timings below are host wall-clock.

**Important:** these numbers are only valid with the `PD_CREATION_DBG` fix
(`pd_creation.h`). That header did `#define PD_CREATION_DBG 0` but tested it
with `#ifdef`, so 16 debug `printf`s were always compiled in and fired *inside*
the timed region of the tracked PD-spawn path. Under QEMU the UART is
instantaneous so they cost nothing; on real hardware each line blocks on the
115200-baud UART for ~6-8 ms. Before the fix the tracked spawn measured 70.9 ms
(an apparent +756% overhead); ~60 ms of that was pure serial I/O.

## Process creation (GPIBM003 untracked / GPIBM004 tracked)

Spawn of `hello_benchmark`, timed from the parent's request to the child's first
instruction (child reports CNTPCT at entry). Excludes kernel boot.

| metric | untracked (sel4utils) | tracked (osm) | overhead |
|---|---|---|---|
| wall-clock (CNTPCT, 24 MHz) | 8.180 ms (σ 6 µs) | 10.230 ms (σ 4 µs) | **+25.1%** |
| CPU cycles (PMU) | 9,817,263 | 12,277,433 | +25.1% |

Per-run wall-clock (µs):
- untracked: 8173, 8176, 8179, 8185, 8189
- tracked:  10227, 10236, 10235, 10227, 10227

## VM boot (GPIVM002 sel4test-vmm / GPIVM004 osm-vmm)

Same Linux 6.1.0 buildroot guest in both. Seconds since u-boot `go`.

| phase | untracked | tracked | delta |
|---|---|---|---|
| seL4 boot | 0.20 ± 0.00 | 0.20 ± 0.00 | +0.00 s |
| guest Linux entry (first guest instr.) | 3.01 ± 0.00 | 4.91 ± 0.00 | **+1.90 s** |
| first userspace (`Run /init`) | 3.89 ± 0.04 | 5.89 ± 0.04 | +2.00 s |
| login prompt | 6.51 ± 0.00 | 13.33 ± 0.06 | **+6.82 s** |

Derived, separating VM *creation* from guest *runtime*:

| interval | untracked | tracked | ratio |
|---|---|---|---|
| VM creation (seL4 boot → guest entry) | 2.81 s | 4.71 s | 1.68× |
| guest kernel boot (entry → `/init`) | 0.88 s | 0.98 s | 1.11× |
| guest userspace init (`/init` → login) | 2.62 s | 7.44 s | **2.84×** |

The tracked VMM's overhead is concentrated in (a) VM creation and (b) guest
userspace init, which is I/O-heavy — every VM exit traverses the tracked path.
The guest *kernel* boot, which is mostly guest-internal compute, is barely
affected. Note that the guest's own printk timestamps cannot show this: they run
on the guest clock and are nearly identical across the two configs (`Run /init`
at [1.044] untracked vs [1.064] tracked). Host-side timestamps are required.

## Linux reference on the same board (Part B)

Board booted to its stock Ubuntu 22.04 (HardKernel BSP kernel 4.9.312-6 aarch64),
static IP 10.42.0.2, driven over ssh. Same `procbench`/`trivial` binaries as the
QEMU experiments (`../qemu-aarch64-startup-bench/`): `fork()`+`execve()` of a
trivial static binary, `clock_gettime(CLOCK_MONOTONIC)`, 300 iterations, 5 runs.

| run | mean (ms) | median (ms) |
|---|---|---|
| 1 | 0.6213 | 0.6099 |
| 2 | 0.6179 | 0.6058 |
| 3 | 0.6202 | 0.6061 |
| 4 | 0.6281 | 0.6080 |
| 5 | 0.6124 | 0.5981 |
| **mean** | **0.620** | **0.606** |

Process creation, all three systems on this board:

| system | time | vs Linux |
|---|---|---|
| Linux (fork+exec)      | 0.620 ms  | 1× |
| seL4 untracked spawn   | 8.180 ms  | 13.2× |
| CellulOS tracked spawn | 10.230 ms | 16.5× |

Under QEMU the same comparison put Linux (27.2 ms) and CellulOS (48.7 ms) within
1.8× of each other. Emulation penalizes the two very unequally: hardware speeds
CellulOS's spawn ~5×, but Linux's fork/exec ~44×, because Linux defers nearly all
the work (COW fork, demand-paged exec) to page faults that are cheap on real
silicon and expensive under TCG. Cross-system startup comparisons under emulation
are therefore systematically misleading; the tracked-vs-untracked comparison,
which holds the kernel constant, is the one that survives the platform change.

### Not possible on this image: Linux as hypervisor

The stock Odroid Ubuntu image's 4.9 BSP kernel is built with `# CONFIG_KVM is not
set` and has no kvm modules, so there is no `/dev/kvm` (the CPUs do start at EL2).
The Linux+KVM VM-boot comparison needs a mainline kernel with KVM enabled.

Raw per-run logs: `{process,vm-untracked,vm-tracked}_run{1..5}.log`
(format: `<seconds since go>\t<line>`), `linux_process_run{1..5}.log`.
