import serial, time, sys
OFF=bytearray([0xa0,0x01,0x00,0xa1]); ON=bytearray([0xa0,0x01,0x01,0xa2])
# relay on ttyUSB0
relay=serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
print("power off..."); relay.write(OFF); time.sleep(1); relay.write(OFF); time.sleep(2)
print("power on...");  relay.write(ON);  time.sleep(1); relay.write(ON)
relay.close()
# read console — try ttyUSB1 first
for dev in ['/dev/ttyUSB1','/dev/ttyUSB0']:
    try:
        c=serial.Serial(dev,115200,timeout=1)
    except Exception as e:
        print(f"{dev}: open failed {e}"); continue
    print(f"--- reading {dev} for 12s ---"); got=b''
    t=time.time()
    while time.time()-t<12:
        d=c.read(256)
        if d: got+=d
    c.close()
    print(f"{dev}: {len(got)} bytes")
    if got:
        sys.stdout.buffer.write(got[:800]); print("\n---end---"); break
