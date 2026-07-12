#!/usr/bin/env python3
"""Sole owner of the Odroid console. Mirrors all serial output to a log file
(so anyone can `tail -f` it read-only) and sends anything written to a FIFO
out to the board. Avoids multi-reader port corruption."""
import serial, os, sys, threading, time

PORT = '/dev/ttyUSB1'; BAUD = 115200
LOG  = '/tmp/odroid-serial.log'
FIFO = '/tmp/odroid-serial.in'

if not os.path.exists(FIFO):
    os.mkfifo(FIFO); os.chmod(FIFO, 0o666)
open(LOG, 'ab').close(); os.chmod(LOG, 0o666)

ser = serial.Serial(PORT, BAUD, timeout=0.2)
print(f"[broker] owning {PORT}@{BAUD}\n[broker] log : {LOG}   (tail -f this)\n[broker] send: echo 'cmd' > {FIFO}", flush=True)

def writer():
    while True:
        with open(FIFO, 'r') as f:          # blocks until someone writes
            for line in f:
                cmd = line.rstrip('\n')
                ser.write((cmd + '\r\n').encode())
                ser.flush()
threading.Thread(target=writer, daemon=True).start()

with open(LOG, 'ab', buffering=0) as lg:
    while True:
        d = ser.read(4096)
        if d:
            lg.write(d)
