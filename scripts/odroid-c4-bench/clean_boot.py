import subprocess, serial, time, sys
def relay(byts):
    subprocess.run(f"printf '{byts}' | sudo tee /dev/ttyUSB0 >/dev/null", shell=True)
print("OFF..."); relay(r'\xa0\x01\x00\xa1'); time.sleep(1); relay(r'\xa0\x01\x00\xa1'); time.sleep(6)
print("ON...");  relay(r'\xa0\x01\x01\xa2'); time.sleep(1); relay(r'\xa0\x01\x01\xa2')
c=serial.Serial('/dev/ttyUSB1',115200,timeout=1)
got=b''; t=time.time()
while time.time()-t<20:
    d=c.read(2048)
    if d: got+=d
c.close()
printable=sum(1 for b in got if 9<=b<=13 or 32<=b<=126)
print(f"\n{len(got)} bytes, printable {printable}/{len(got)}")
print("--- decoded ---"); sys.stdout.write(''.join(chr(b) if 32<=b<=126 else ('\n' if b in (10,13) else '.') for b in got[:600]))
print("\n--- hex (first 64) ---", got[:64].hex())
