import subprocess, serial, time, sys
def relay(b): subprocess.run(f"printf '{b}' | sudo tee /dev/ttyUSB0 >/dev/null", shell=True)
relay(r'\xa0\x01\x00\xa1'); time.sleep(1); relay(r'\xa0\x01\x00\xa1'); time.sleep(4)
relay(r'\xa0\x01\x01\xa2'); time.sleep(1); relay(r'\xa0\x01\x01\xa2')
c=serial.Serial('/dev/ttyUSB1',115200,timeout=1); got=b''; t=time.time()
while time.time()-t<25:
    d=c.read(4096)
    if d: got+=d
c.close()
p=sum(1 for x in got if 9<=x<=13 or 32<=x<=126)
print(f"=== {len(got)} bytes, clean={p/len(got):.0%}\n" if got else "=== NO DATA\n")
txt=''.join(chr(x) if (32<=x<=126 or x in (10,13)) else '.' for x in got)
sys.stdout.write(txt[:2500])
