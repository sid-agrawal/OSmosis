import serial, time, sys
OFF=bytearray([0xa0,0x01,0x00,0xa1]); ON=bytearray([0xa0,0x01,0x01,0xa2])
relay=serial.Serial('/dev/ttyUSB0',9600,timeout=1)
relay.write(OFF); time.sleep(1); relay.write(OFF); time.sleep(2)
relay.write(ON);  time.sleep(1); relay.write(ON)
relay.close()
c=serial.Serial('/dev/ttyUSB1',115200,timeout=1)
got=b''; t=time.time()
while time.time()-t<18:
    d=c.read(1024)
    if d: got+=d
c.close()
print(f"captured {len(got)} bytes at 115200")
# printable ratio to judge baud
printable=sum(1 for b in got if 9<=b<=13 or 32<=b<=126)
print(f"printable ratio: {printable}/{len(got)}" + (f" = {printable/len(got):.0%}" if got else ""))
sys.stdout.buffer.write(got[:1500])
