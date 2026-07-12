import serial, time, sys
for dev in ['/dev/ttyUSB1','/dev/ttyUSB0']:
    try:
        c = serial.Serial(dev, 115200, timeout=1)
    except Exception as e:
        print(f"{dev}: open failed: {e}"); continue
    got = b''; t = time.time()
    while time.time() - t < 8:
        d = c.read(512)
        if d: got += d
    c.close()
    print(f"{dev} @115200: {len(got)} bytes")
    if got:
        sys.stdout.buffer.write(got[-1200:]); print("\n--- end ---\n")
