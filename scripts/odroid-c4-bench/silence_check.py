import subprocess, serial, time
def relay(b): subprocess.run(f"printf '{b}' | sudo tee /dev/ttyUSB0 >/dev/null", shell=True)
print("power OFF x2"); relay(r'\xa0\x01\x00\xa1'); time.sleep(1); relay(r'\xa0\x01\x00\xa1'); time.sleep(4)
print("power ON x2");  relay(r'\xa0\x01\x01\xa2'); time.sleep(1); relay(r'\xa0\x01\x01\xa2')
c=serial.Serial('/dev/ttyUSB1',115200,timeout=1); got=b''; t=time.time()
while time.time()-t<15:
    d=c.read(2048)
    if d: got+=d
c.close()
p=sum(1 for x in got if 32<=x<=126)
print(f"\nRESULT: {len(got)} bytes in 15s" + (f", {p} printable ({p/len(got):.0%})" if got else " -> TOTAL SILENCE"))
if got:
    print("sample:", ''.join(chr(x) if 32<=x<=126 else '.' for x in got[:200]))
