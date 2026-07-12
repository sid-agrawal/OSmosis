#!/usr/bin/env python3
"""Drive a root shell on the Odroid-C4's Linux (Ubuntu) over the serial console.

Logs in if needed, then runs commands and returns their output. Used to bootstrap
networking on the board so the rest of Part B can go over SSH.
"""
import serial
import time

PORT = "/dev/ttyUSB1"
BAUD = 115200
USER = "root"
PASSWORD = "odroid"
PROMPT = "root@odroid"


class SerialShell:
    def __init__(self, port=PORT, baud=BAUD):
        self.con = serial.Serial(port, baud, timeout=0.2)

    def _wait(self, pat, timeout=30):
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            buf += self.con.read(4096)
            if pat.encode() in buf[-500:]:
                return True, buf
        return False, buf

    def login(self):
        """Get to a root prompt, logging in only if we aren't already there."""
        self.con.write(b"\n")
        time.sleep(1.5)
        self.con.reset_input_buffer()
        self.con.write(b"\n")
        ok, buf = self._wait(PROMPT, 6)
        if ok:
            return True
        ok, _ = self._wait("login:", 20)
        if not ok:
            raise RuntimeError("no login prompt on console")
        self.con.write((USER + "\n").encode())
        if not self._wait("Password:", 10)[0]:
            raise RuntimeError("no password prompt")
        time.sleep(0.5)
        self.con.write((PASSWORD + "\n").encode())
        if not self._wait(PROMPT, 20)[0]:
            raise RuntimeError("login failed")
        return True

    def run(self, cmd, timeout=60):
        """Run cmd, return its stdout+stderr (between unique markers)."""
        self.con.reset_input_buffer()
        marker = f"__D{int(time.time()*1000) % 100000}__"
        self.con.write(f"{cmd}; echo {marker}\n".encode())
        self.con.flush()
        ok, buf = self._wait(marker, timeout)
        text = buf.decode("utf-8", "replace").replace("\r", "")
        lines = text.split("\n")
        # drop the echoed command line and everything from the marker onward
        out = []
        for ln in lines[1:]:
            if marker in ln:
                break
            out.append(ln)
        return "\n".join(out).strip()

    def close(self):
        self.con.close()


if __name__ == "__main__":
    import sys
    sh = SerialShell()
    sh.login()
    print(sh.run(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "uname -a"))
    sh.close()
