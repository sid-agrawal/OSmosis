import serial, time, sys
sys.stdout.reconfigure(line_buffering=True)
KW = ('u-boot','hardkernel','odroid','=>','sel4','booting','starting','crc','dram','net:')
def openport():
    while True:
        try: return serial.Serial('/dev/ttyUSB1',115200,timeout=0.2)
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} open failed ({e}); retrying", flush=True); time.sleep(1)
c = openport(); buf=b''; last=time.time()
while True:
    try: d=c.read(4096)
    except Exception:
        print(f"{time.strftime('%H:%M:%S')} port error; reopening", flush=True); c=openport(); buf=b''; continue
    if d: buf+=d
    now=time.time()
    if now-last>=2:
        ts=time.strftime('%H:%M:%S')
        if buf:
            p=sum(1 for b in buf if 9<=b<=13 or 32<=b<=126); r=p/len(buf)
            txt=''.join(chr(b) if 32<=b<=126 else '.' for b in buf)[-55:]
            low=bytes(b for b in buf if 32<=b<=126).decode('ascii','ignore').lower()
            flag=next((' <<CLEAN:'+k+'>>' for k in KW if k in low),'')
            print(f"{ts} {len(buf):>4}B clean={r:>4.0%} | {txt}{flag}")
        else:
            print(f"{ts}    0B (no data)")
        buf=b''; last=now
