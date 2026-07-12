#!/usr/bin/env python3
"""Unattended §7.1 benchmark campaign on the Odroid-C4.

Drives the USB relay to power-cycle the board, interrupts u-boot, TFTPs a
CellulOS image and boots it, then captures the serial console with host-side
timestamps on every line.

Configs:
  process     GPIBM003 (untracked, sel4utils spawn) + GPIBM004 (tracked, osm spawn)
  vm-untracked GPIVM002 (sel4test-vmm, Linux guest)
  vm-tracked   GPIVM004 (osm-vmm, Linux guest)
"""
import re
import sys
import time
import serial
import pathlib
import argparse

RELAY = "/dev/ttyUSB0"
CONSOLE = "/dev/ttyUSB1"
RELAY_OFF = bytes([0xA0, 0x01, 0x00, 0xA1])
RELAY_ON = bytes([0xA0, 0x01, 0x01, 0xA2])
BOARD_IP = "10.42.0.2"
HOST_IP = "10.42.0.1"
LOAD_ADDR = "0x20000000"

RESULTS = pathlib.Path(__file__).parent / "results"

CONFIGS = {
    "process": dict(img="image", done=r"All is well in the universe", timeout=120),
    "vm-untracked": dict(img="vm-untracked", done=r"buildroot login:", timeout=180),
    "vm-tracked": dict(img="vm-tracked", done=r"buildroot login:", timeout=180),
}


def power(state):
    with serial.Serial(RELAY, 9600, timeout=1) as r:
        r.write(RELAY_ON if state else RELAY_OFF)
        r.flush()


def power_cycle():
    power(False)
    time.sleep(3)
    power(True)


def run_once(cfg_name, run_idx):
    cfg = CONFIGS[cfg_name]
    log_path = RESULTS / f"{cfg_name}_run{run_idx}.log"
    lines = []

    with serial.Serial(CONSOLE, 115200, timeout=0.1) as con:
        con.reset_input_buffer()
        power_cycle()

        # Spam newlines to catch the ~2 s autoboot window.
        buf = b""
        deadline = time.monotonic() + 45
        at_prompt = False
        while time.monotonic() < deadline:
            con.write(b"\n")
            time.sleep(0.08)
            buf += con.read(4096)
            if b"=> " in buf[-200:] or buf.rstrip().endswith(b"=>"):
                at_prompt = True
                break
        if not at_prompt:
            RESULTS.mkdir(exist_ok=True)
            log_path.write_bytes(b"### NO_UBOOT_PROMPT; raw serial:\n" + buf)
            return dict(config=cfg_name, run=run_idx, status="NO_UBOOT_PROMPT", log=str(log_path))

        time.sleep(0.5)
        con.reset_input_buffer()
        for cmd in (
            f"setenv ipaddr {BOARD_IP}",
            f"setenv serverip {HOST_IP}",
            f"tftpboot {LOAD_ADDR} {cfg['img']}",
        ):
            con.write((cmd + "\n").encode())
            con.flush()
            time.sleep(1.0)

        # Wait for TFTP to finish ("Bytes transferred").
        tftp_deadline = time.monotonic() + 90
        tbuf = b""
        while time.monotonic() < tftp_deadline:
            tbuf += con.read(4096)
            if b"Bytes transferred" in tbuf:
                break
        else:
            RESULTS.mkdir(exist_ok=True)
            log_path.write_bytes(b"### TFTP_TIMEOUT; raw serial after uboot prompt:\n" + tbuf)
            return dict(config=cfg_name, run=run_idx, status="TFTP_TIMEOUT", log=str(log_path))

        # Boot. t0 = the instant we release the CPU into the image.
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
                ts = time.monotonic() - t0
                text = raw.decode("utf-8", "replace").rstrip("\r")
                lines.append((ts, text))
            # The login prompt has no trailing newline, so it never becomes a
            # complete line; match against the unterminated tail as well.
            tail = "\n".join(t for _, t in lines[-40:]) + \
                "\n" + partial.decode("utf-8", "replace")
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
        f.write(f"# config={cfg_name} run={run_idx} status={status}\n")
        f.write("# t_sec_since_go\ttext\n")
        for ts, text in lines:
            f.write(f"{ts:9.4f}\t{text}\n")

    return dict(config=cfg_name, run=run_idx, status=status, log=str(log_path),
                lines=lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--configs", nargs="*", default=list(CONFIGS))
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    summary = []
    for cfg_name in args.configs:
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
