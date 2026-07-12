#!/usr/bin/env python3
"""Boot the Odroid-C4's Ubuntu with a KVM-enabled kernel, via TFTP from u-boot.

The board's stock HardKernel kernel (4.9 BSP) is built with CONFIG_KVM disabled,
so Linux-as-hypervisor experiments cannot run on it. Ubuntu's own 5.15 arm64
kernel has CONFIG_KVM=y and ships the mainline Odroid-C4 device tree.

This loads that kernel + initrd + mainline DTB over TFTP and boots it against the
existing on-SD root filesystem. Nothing on the SD card is modified: a plain power
cycle boots the stock 4.9 kernel exactly as before.
"""
import re
import sys
import time
import serial

RELAY, CONSOLE = "/dev/ttyUSB0", "/dev/ttyUSB1"
OFF, ON = bytes([0xA0, 0x01, 0x00, 0xA1]), bytes([0xA0, 0x01, 0x01, 0xA2])
ROOT_UUID = "e139ce78-9841-40fe-8823-96a304a09859"

# u-boot loads: keep kernel/dtb/initrd far enough apart for their sizes
# (Image ~47 MB, initrd ~42 MB).
K_ADDR, DTB_ADDR, INITRD_ADDR = "0x08000000", "0x10000000", "0x14000000"


def power(state):
    with serial.Serial(RELAY, 9600, timeout=1) as r:
        r.write(ON if state else OFF)
        r.flush()


def main():
    con = serial.Serial(CONSOLE, 115200, timeout=0.05)
    con.reset_input_buffer()
    power(False)
    time.sleep(3)
    power(True)

    # The vendor u-boot (2015.01) gives a ~2 s window and wants Enter/space/Ctrl+C.
    buf = b""
    t0 = time.time()
    at_prompt = False
    while time.time() - t0 < 30:
        con.write(b"\x03")
        con.write(b"\r\n")
        con.write(b" ")
        time.sleep(0.05)
        buf += con.read(8192)
        if re.search(rb"(odroidc4#|=>)\s*$", buf[-80:]):
            at_prompt = True
            break
    if not at_prompt:
        print("FAILED: no u-boot prompt")
        return 1
    print("at u-boot prompt")

    time.sleep(0.5)
    con.reset_input_buffer()
    cmds = [
        "setenv ipaddr 10.42.0.2",
        "setenv serverip 10.42.0.1",
        f"tftp {INITRD_ADDR} initrd515",
        "setenv isize ${filesize}",
        f"tftp {DTB_ADDR} dtb515",
        f"tftp {K_ADDR} Image515",
        f'setenv bootargs "root=UUID={ROOT_UUID} rootwait rw '
        'console=ttyS0,115200n8 net.ifnames=0"',
        f"booti {K_ADDR} {INITRD_ADDR}:" + "${isize} " + DTB_ADDR,
    ]
    out = b""
    for c in cmds:
        con.write((c + "\n").encode())
        con.flush()
        t = time.time()
        limit = 60 if c.startswith("tftp") else 2
        while time.time() - t < limit:
            out += con.read(8192)
            if c.startswith("tftp") and b"Bytes transferred" in out[-300:]:
                break
    print("--- u-boot output (tail) ---")
    print(out[-600:].decode("utf-8", "replace").replace("\r", ""))

    t0 = time.time()
    boot = b""
    while time.time() - t0 < 120:
        boot += con.read(8192)
        if b"login:" in boot[-200:]:
            break
    con.close()

    txt = boot.decode("utf-8", "replace").replace("\r", "")
    with open("/tmp/boot515.log", "w") as f:
        f.write(txt)
    for pat in (r"Linux version \S+", r"Booting Linux", r"kvm.*", r"Kernel panic.*"):
        for m in re.findall(pat, txt, re.I)[:3]:
            print("  ", m[:100])
    print("--- boot tail ---")
    print(txt[-500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
