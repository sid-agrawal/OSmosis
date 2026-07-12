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

Same Linux 6.1.0 buildroot guest (same kernel binary, same 766 KB initramfs, same
256 MB guest RAM) in both. t0 = the VMM begins creating the guest ("Running test
GPIVM00x"), NOT the ELF-loader: seL4 boot + sel4test init take ~2.4 s and print
heavily, and folding them into "VM creation" badly distorts it.

**These numbers required a second print fix.** `apps/vmm/src/osm-vmm/vmm.c` called
`pd_client_dump()` unconditionally while creating a guest, printing a CSV row per
model node and edge (~220 lines = ~1.1 s of blocking UART) *inside* the timed
VM-creation phase. Now gated behind `GPIExtractModel` (as sel4test-tests already
was). Same class of bug as `PD_CREATION_DBG` above: on real hardware, serial I/O
inside a timed region is the thing to audit first.

| phase (cumulative from VMM start) | untracked | tracked | ratio | Linux+KVM |
|---|---|---|---|---|
| p1 first guest instruction | 0.40 ± 0.00 s | 1.30 ± 0.00 s | 3.25x | 0.18 s |
| p3 first userspace | 1.28 ± 0.04 s | 2.24 ± 0.05 s | 1.75x | 0.47 s |
| p4 login prompt | 3.87 ± 0.05 s | 9.70 ± 0.08 s | 2.51x | 2.72 s |

Decomposed into intervals:

| interval | untracked | tracked | ratio | Linux+KVM |
|---|---|---|---|---|
| VM creation (-> guest's 1st instr) | 0.40 s | 1.30 s | 3.25x | 0.18 s |
| guest kernel boot (-> /init) | 0.88 s | 0.94 s | 1.07x | 0.29 s |
| guest userspace init (-> login) | 2.59 s | 7.46 s | **2.88x** | 2.25 s |

The overhead is concentrated in (a) VM creation and (b) guest userspace init.

Note that CellulOS does **not** cause more VM exits -- the guest is byte-identical
and makes the same device accesses. Each exit is *more expensive*. On every exit the
fault handler must read the guest's registers, decode the instruction, and write
them back (`apps/vmm/src/arch/aarch64/fault.c`). The untracked VMM does this with a
direct seL4 syscall (`seL4_TCB_{Read,Write}Registers`, sel4test-vmm/vmm.c:64,70);
the tracked VMM does it via `cpu_client_{read,write}_registers` (osm-vmm/vmm.c:64,69)
-- an IPC RPC to the GPI CPU component, a *separate PD*, which then makes that same
syscall. So every exit pays at least two extra cross-PD round-trips. This is the GPI
architecture (the vCPU is a mediated resource), not model bookkeeping per se.

That predicts the phase pattern exactly: guest *kernel* boot is guest-internal
compute with few exits and is barely affected (1.07x), while guest *userspace* init
is device-probing and console I/O -- exit-heavy -- and pays 2.88x. (We did not count
exits, so the per-exit cost is not attributed further.) Note the guest's own printk
timestamps cannot show any of this: they run on the guest clock and are nearly
identical across configs (`Run /init` at [1.044] untracked vs [1.068] tracked)
while the host-side gap for that phase is ~1 s. Host-side timestamps are required.

The untracked seL4 VMM is competitive with Linux+KVM (3.87 s vs 2.72 s to login,
1.4x); CellulOS's tracked VMM is 3.6x KVM. An earlier version of these numbers
(t0 at the ELF-loader, model dump still on) put VM creation at 2.81/4.71 s and
made seL4's VMM look ~15x slower than KVM at creation. That was an artifact of
both mistakes; it is not true.

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

### Linux as hypervisor: not possible on the *stock* image

The stock Odroid Ubuntu image's 4.9 BSP kernel is built with `# CONFIG_KVM is not
set` and has no kvm modules, so there is no `/dev/kvm` (the CPUs do start at EL2).
We fixed this by rebuilding the kernel -- see the KVM section below.

Raw per-run logs: `{process,vm-untracked,vm-tracked}_run{1..5}.log`
(format: `<seconds since go>\t<line>`), `linux_process_run{1..5}.log`.

## Enabling Linux + KVM on the board

The stock image cannot run KVM. To get that comparison we rebuilt the board's own
kernel (hardkernel/linux, branch `odroidg12-4.9.y`, 4.9.337) with:

1. `CONFIG_KVM=y` / `CONFIG_KVM_ARM_HOST=y`, and
2. a device-tree fix (`../odroid-c4-kvm-gic.patch`): the vendor DTS declares only
   the GIC-400's GICD and a truncated GICC, omitting GICH (hypervisor control) and
   GICV (virtual CPU interface). KVM's vGICv2 needs all four, so the vendor kernel
   could not have run KVM even with the config flag on.

Cross-compiled with gcc-11 (gcc-13 is too new for a 4.9 tree). After that:
`kvm: Hyp mode initialized successfully`, `kvm: vgic-v2@ffc04000`, `/dev/kvm`
present, `KVM_GET_API_VERSION = 12`. Installed to `/media/boot` (originals backed
up as `*.orig`), so it is persistent across reboots.

Measurement: the *identical* guest CellulOS's VMM boots
(`apps/vmm/board/odroidc4/{linux,rootfs.cpio.gz}`), same 256 MB of guest memory,
under `qemu-system-aarch64` 6.2 with `-enable-kvm -cpu host -M virt,gic-version=2`.
t0 = qemu launch. N=5, `bench_kvm_vm.py`. Results are in the VM-boot table above.

### What the QEMU experiments got wrong about KVM

Under QEMU, Linux+KVM took 73 s vs seL4's 6.1 s, and thesis §7.1 argued that was an
emulated-EL2 artifact that would vanish on hardware. That was right: on hardware
Linux+KVM boots the same guest to login in 2.72 s. But the seL4 VMM is *not* far
behind -- the untracked one reaches login in 3.87 s (1.4x). CellulOS's tracked VMM,
at 9.70 s, is 3.6x KVM, and that gap is model-tracking cost, not VMM inefficiency.

### A hypothesis we tested and rejected

We suspected the seL4 VMMs were slow to create a VM because they eagerly allocate,
zero and map all 256 MB of guest RAM (128 x 2 MB frames, each retyped from untyped,
cnode-copied, and mapped into both the guest's and the VMM's address space) plus
memcpy the 13.9 MB kernel image -- while KVM demand-pages guest RAM on stage-2
faults. Forcing QEMU to do the eager thing (`-mem-prealloc`) costs only **+50 ms**
(0.178 s -> 0.228 s), so populating 256 MB is not what costs time. With the correct
t0 and the model dump removed, seL4's VM creation is 0.40 s against KVM's 0.18 s,
and there is no large gap left to explain.
