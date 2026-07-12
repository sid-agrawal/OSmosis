#!/usr/bin/env python3
"""Time a Linux+KVM guest boot on the Odroid-C4, in the same phases as the
seL4/CellulOS VMM measurements.

Runs on the board. Boots the *identical* guest image that CellulOS's VMM boots
(apps/vmm/board/odroidc4/{linux,rootfs.cpio.gz}), with the same 256 MB of guest
memory, under qemu-system-aarch64 with KVM.

t0 is the moment the VMM (qemu) is launched, matching "from the VMM beginning
guest creation". Phases:
  p1/p2  first guest instruction   -> first guest kernel output
  p3     first userspace           -> "Run /init as init process"
  p4     login prompt              -> "buildroot login:"
"""
import re
import sys
import time
import subprocess

QEMU = [
    "qemu-system-aarch64",
    "-M", "virt,gic-version=2",
    "-cpu", "host",
    "-enable-kvm",
    "-smp", "1",
    "-m", "256M",
    "-nographic",
    "-kernel", "/root/linux",
    "-initrd", "/root/rootfs.cpio.gz",
    "-append", "console=ttyAMA0",
]

MARKERS = [
    ("p1_first_guest_instr", re.compile(rb"Linux version")),
    ("p3_first_userspace", re.compile(rb"Run /init as init process")),
    ("p4_login_prompt", re.compile(rb"buildroot login:")),
]


def one_run(timeout=120):
    p = subprocess.Popen(QEMU, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, bufsize=0)
    t0 = time.monotonic()
    hits, buf = {}, b""
    try:
        while time.monotonic() - t0 < timeout:
            chunk = p.stdout.read(1)          # login prompt has no trailing newline
            if not chunk:
                break
            buf += chunk
            for name, pat in MARKERS:
                if name not in hits and pat.search(buf[-200:]):
                    hits[name] = time.monotonic() - t0
            if len(hits) == len(MARKERS):
                break
    finally:
        p.kill()
        p.wait()
    return hits


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    runs = []
    for i in range(1, n + 1):
        h = one_run()
        runs.append(h)
        print(f"run {i}: " + "  ".join(f"{k}={v:.3f}s" for k, v in h.items()),
              flush=True)
        time.sleep(2)

    print("\n=== means (N=%d) ===" % len(runs))
    for name, _ in MARKERS:
        vals = [r[name] for r in runs if name in r]
        if vals:
            mean = sum(vals) / len(vals)
            sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            print(f"{name:24s} {mean:6.3f} s  (sd {sd:.3f}, n={len(vals)})")


if __name__ == "__main__":
    main()
