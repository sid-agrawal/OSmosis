#!/usr/bin/env python3
"""§7.1 benchmark campaign on the Odroid-C4, loading images from the SD card.

Companion to campaign.py, which TFTPs the image from u-boot. That works with the
CellulOS SD card (mainline u-boot 2023.07), but with HardKernel's Ubuntu card
(vendor u-boot 2015.01) the ethernet drops most TFTP data packets and the
transfer never completes. Since the Ubuntu card is what we now boot (it carries
the KVM-enabled kernel), stage the image onto its FAT boot partition over ssh
instead and have u-boot `load mmc` it -- no network involved in the boot path.

Per config: boot Ubuntu once, scp the image to /media/boot, then for each run
power-cycle, interrupt u-boot, `load mmc` + `go`, and capture the console with
host-side timestamps.
"""
import os
import re
import sys
import time
import serial
import pathlib
import argparse
import subprocess

RELAY, CONSOLE = "/dev/ttyUSB0", "/dev/ttyUSB1"
OFF, ON = bytes([0xA0, 0x01, 0x00, 0xA1]), bytes([0xA0, 0x01, 0x01, 0xA2])
BOARD = "10.42.0.2"
LOAD_ADDR = "0x20000000"
RESULTS = pathlib.Path(__file__).parent / "results"
TFTP_DIR = pathlib.Path("/srv/tftp")

CONFIGS = {
    "vm-untracked": dict(img="vm-untracked", done=r"buildroot login:", timeout=180),
    "vm-tracked": dict(img="vm-tracked", done=r"buildroot login:", timeout=180),
    "process": dict(img="image", done=r"All is well in the universe", timeout=120),
}

# We run under sudo (for the serial ports), but the ssh keys belong to the
# invoking user, so drop privileges for anything that talks to the board over ssh.
USER = os.environ.get("SUDO_USER") or os.environ.get("USER") or "siagraw"
ASUSER = ["sudo", "-u", USER]
SSH = ASUSER + ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
                f"root@{BOARD}"]


def power(state):
    with serial.Serial(RELAY, 9600, timeout=1) as r:
        r.write(ON if state else OFF)
        r.flush()


def power_cycle():
    power(False)
    time.sleep(3)
    power(True)


def wait_for_ssh(timeout=120):
    """Let the board autoboot into Ubuntu and wait for it to answer ssh."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(SSH + ["true"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return True
        time.sleep(5)
    return False


def stage(cfg_name):
    """Copy the image onto the board's FAT boot partition (needs Ubuntu up)."""
    img = CONFIGS[cfg_name]["img"]
    print(f"  staging {img} -> board:/media/boot/{img} ...", flush=True)
    power_cycle()
    if not wait_for_ssh():
        raise RuntimeError("board did not come up for staging")
    subprocess.run(SSH + ["rm -f /media/boot/selimg"], check=False,
                   stdout=subprocess.DEVNULL)
    subprocess.run(ASUSER + ["scp", "-o", "StrictHostKeyChecking=no",
                             str(TFTP_DIR / img), f"root@{BOARD}:/media/boot/selimg"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(SSH + ["sync"], check=False, stdout=subprocess.DEVNULL)
    print("  staged.", flush=True)


def at_uboot(con, timeout=45):
    """Interrupt autoboot. Vendor u-boot wants Enter/space/Ctrl+C; mainline "=>"."""
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        con.write(b"\x03")
        con.write(b"\r\n")
        con.write(b" ")
        time.sleep(0.06)
        buf += con.read(8192)
        if re.search(rb"(odroidc4#|=>)\s*$", buf[-120:]):
            return True
    return False


def run_once(cfg_name, run_idx):
    cfg = CONFIGS[cfg_name]
    log_path = RESULTS / f"{cfg_name}_run{run_idx}.log"
    lines = []

    with serial.Serial(CONSOLE, 115200, timeout=0.1) as con:
        con.reset_input_buffer()
        power_cycle()
        if not at_uboot(con):
            return dict(config=cfg_name, run=run_idx, status="NO_UBOOT_PROMPT")

        time.sleep(0.5)
        con.reset_input_buffer()
        con.write(f"load mmc 1:1 {LOAD_ADDR} selimg\n".encode())
        con.flush()
        lbuf = b""
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            lbuf += con.read(8192)
            if b"bytes read" in lbuf:
                break
        else:
            RESULTS.mkdir(exist_ok=True)
            log_path.write_bytes(b"### MMC_LOAD_FAILED\n" + lbuf)
            return dict(config=cfg_name, run=run_idx, status="MMC_LOAD_FAILED")

        con.write(f"go {LOAD_ADDR}\n".encode())
        con.flush()
        t0 = time.monotonic()

        done = re.compile(cfg["done"])
        deadline = t0 + cfg["timeout"]
        partial = b""
        status = "TIMEOUT"
        while time.monotonic() < deadline:
            chunk = con.read(4096)
            if not chunk:
                continue
            partial += chunk
            while b"\n" in partial:
                raw, partial = partial.split(b"\n", 1)
                lines.append((time.monotonic() - t0,
                              raw.decode("utf-8", "replace").rstrip("\r")))
            tail = "\n".join(t for _, t in lines[-40:]) + "\n" + \
                partial.decode("utf-8", "replace")
            if done.search(tail):
                if partial.strip():
                    lines.append((time.monotonic() - t0,
                                  partial.decode("utf-8", "replace").rstrip("\r")))
                    partial = b""
                status = "OK"
                break
        if partial.strip():
            lines.append((time.monotonic() - t0,
                          partial.decode("utf-8", "replace").rstrip("\r")))

    RESULTS.mkdir(exist_ok=True)
    with open(log_path, "w") as f:
        f.write(f"# config={cfg_name} run={run_idx} status={status} src=mmc\n")
        f.write("# t_sec_since_go\ttext\n")
        for ts, text in lines:
            f.write(f"{ts:9.4f}\t{text}\n")
    return dict(config=cfg_name, run=run_idx, status=status)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--configs", nargs="*", default=["vm-untracked", "vm-tracked"])
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    summary = []
    for cfg_name in args.configs:
        stage(cfg_name)
        for i in range(1, args.runs + 1):
            print(f"[{time.strftime('%H:%M:%S')}] {cfg_name} run {i}/{args.runs} ...",
                  flush=True)
            try:
                res = run_once(cfg_name, i)
            except Exception as e:
                res = dict(config=cfg_name, run=i, status=f"ERROR:{e}")
            print(f"    -> {res['status']}", flush=True)
            summary.append(res)

    power(False)
    print("\n=== CAMPAIGN SUMMARY ===")
    for r in summary:
        print(f"{r['config']:14s} run{r['run']}  {r['status']}")


if __name__ == "__main__":
    sys.exit(main())
