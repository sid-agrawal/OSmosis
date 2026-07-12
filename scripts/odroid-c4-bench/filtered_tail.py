import serial, time, sys, re
sys.stdout.reconfigure(line_buffering=True)
KEY  = re.compile(r'(U-Boot|ODROID|Hit any key|=>|Starting application|DRAM|MMC:|Net:|Autoboot|bl31|BL33|Card did not|unable|fail)', re.I)
LOOP = re.compile(r'(LOOP:|EMMC:|NAND:|USB:8|SD\?)', re.I)
def openp():
    while True:
        try: return serial.Serial('/dev/ttyUSB1',115200,timeout=0.3)
        except Exception as e:
            print(f"[open failed: {e}; retry]"); time.sleep(1)
c=openp(); buf=b''; last_loop=0; loops=0
print("[filtered console tail up — quiet unless real boot output appears]")
while True:
    try: d=c.read(4096)
    except Exception:
        print("[port error; reopening]"); c=openp(); buf=b''; continue
    if not d: continue
    buf+=d
    while b'\n' in buf or len(buf)>512:
        if b'\n' in buf: line,buf = buf.split(b'\n',1)
        else:            line,buf = buf[:512], buf[512:]
        txt=''.join(chr(b) for b in line if 32<=b<=126).strip()
        if len(txt) < 4: continue
        if LOOP.search(txt):
            loops+=1; now=time.time()
            if now-last_loop > 15:
                print(f"[bootROM still looping, no bootloader found — {loops} scans]")
                last_loop=now; loops=0
            continue
        if KEY.search(txt):
            print(f">> {txt[:130]}")
