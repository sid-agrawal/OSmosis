import serial, time, sys
for baud in [115200, 921600, 1500000, 750000, 500000, 250000, 57600, 38400, 9600]:
    try:
        c = serial.Serial('/dev/ttyUSB1', baud, timeout=0.5)
    except Exception as e:
        print(f"{baud}: {e}"); continue
    c.reset_input_buffer()
    c.write(b'\r\n'); time.sleep(0.6)
    got = c.read(400); c.close()
    printable = sum(1 for b in got if 9<=b<=13 or 32<=b<=126)
    ratio = (printable/len(got)) if got else 0
    snip = bytes(b if 32<=b<=126 else 46 for b in got[:60]).decode('ascii','replace')
    print(f"baud={baud:>7}  bytes={len(got):>3}  printable={ratio:>4.0%}  | {snip}")
