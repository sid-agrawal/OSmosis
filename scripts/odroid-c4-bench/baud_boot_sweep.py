import subprocess, serial, time, sys
def relay(b): subprocess.run(f"printf '{b}' | sudo tee /dev/ttyUSB0 >/dev/null", shell=True)
def cycle():
    relay(r'\xa0\x01\x00\xa1'); time.sleep(1); relay(r'\xa0\x01\x00\xa1'); time.sleep(4)
    relay(r'\xa0\x01\x01\xa2'); time.sleep(1); relay(r'\xa0\x01\x01\xa2')
for baud in [115200, 230400, 57600, 1500000]:
    subprocess.run("sudo fuser -k /dev/ttyUSB1 2>/dev/null", shell=True); time.sleep(1)
    cycle()
    c=serial.Serial('/dev/ttyUSB1',baud,timeout=1); got=b''; t=time.time()
    while time.time()-t<12:
        d=c.read(2048)
        if d: got+=d
    c.close()
    printable=sum(1 for x in got if 9<=x<=13 or 32<=x<=126)
    r=(printable/len(got)) if got else 0
    snip=''.join(chr(x) if 32<=x<=126 else '.' for x in got[:70])
    print(f"baud={baud:>7} bytes={len(got):>4} printable={r:>4.0%} | {snip}")
