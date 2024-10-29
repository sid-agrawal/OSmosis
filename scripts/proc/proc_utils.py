import os
import psutil
import sys
from read_pagemap import SystemRAMRange

def convert_iomem_to_RAMranges(iomem_output: str) -> list[SystemRAMRange]:
    """
    Given the output of the iomem command obtained previously.
    Convert it to SystemRamRange
    """
    page_size = os.sysconf("SC_PAGE_SIZE")
    assert page_size != 0, "cannot determine system page size"
    ret_val :list[SystemRAMRange] = []
    for ln in iomem_output.splitlines():        
        ln = ln.strip('\n')      
        if ln.endswith("System RAM"):
            toks = ln.split(None, 2)
            (a0, a1) = toks[0].split('-')
            astart = int(a0, 16)
            aend = int(a1, 16)
            if astart == 0 and aend == 0:
                # Kernel reports range as 00000000-00000000. We're not privileged enough.
                print("error: /proc/iomem is not disclosing memory addresses. Run with increased privilege.", file=sys.stderr)
                sys.exit(1)
            assert aend > astart, "invalid system memory range: %s" % ln
            size = aend+1 - astart
            if False:
                # Although system RAM blocks would normally be well aligned, they don't have to be, so disable this check.
                assert (astart % page_size) == 0, "error: /proc/iomem entry not %u-aligned: %s" % (page_size, ln)
                assert (size % page_size) == 0, "error: /proc/iomem entry size not multiple of %u: %s" % (page_size, ln)
            ret_val.append(SystemRAMRange(astart, size))
    
    return ret_val

def getPIDByName(name :str) -> list[int]:
    pids: list[int] = []
    for proc in psutil.process_iter():
        if proc.name().startswith(name):
            pids.append(proc.pid)
            print(f"NAME: {proc.name()}\t PID: {proc.pid}")
    
    return pids

'''
def get_guest_host_mappings(
    phandle: pexpect.spawn, g2h_file: str
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:

    # Get host to guest to host mappings
    phandle.sendline("cat /proc/iomem")
    phandle.expect("#")
    iomem_output = phandle.before.decode()

    gpa2hpa = []
    gpa2hva = []
    page_size = os.sysconf("SC_PAGE_SIZE")
    assert page_size != 0, "cannot determine system page size"
    print(f"SC_PAGE_SIZE: {sizeof_fmt(page_size)} ")

    pexpect_handle = pexpect.spawn(telnet_cmd)
    pexpect_handle.expect("(qemu)")
    iommem_ranges = convert_iomem_to_RAMranges(iomem_output)

    start_time = time.time()
    ###########
    # limit = 2000
    # count = 0
    ###########

    for idx in range(len(iommem_ranges)):
        x = iommem_ranges[idx]
        print(
            f"START = IOMem Range [{idx}] {x.start:<16x} "
            f"{x.start + x.size:<16x} {x.size/page_size} Pages "
        )
        offset = 0

        while offset < x.size:
            gpa = x.start + offset
            hpa = get_guest_host_translation(
                QemuMonitorCommand.GPA2HPA, gpa, pexpect_handle
            )
            hva = get_guest_host_translation(
                QemuMonitorCommand.GPA2HVA, gpa, pexpect_handle
            )

            gpa2hpa.append((gpa, hpa))
            gpa2hva.append((gpa, hva))

            # with open("Output.txt", "a") as text_file:
            #     print(f"gPA : 0x{gpa:<16x} ---> hVA: 0x{hva:<16x}"
            #           f" hPA: 0x{hpa:<16x} ", file=text_file)

            page_offset = offset / page_size
            num_pages = int(x.size / page_size)

            if page_offset % 512 == 0:
                print(
                    f"\t{time.time() - start_time:4.2f} seconds:  "
                    f"{page_offset/num_pages * 100:.2f}%"
                )

            # Update offset
            offset += page_size

            # if (count >= limit):
            #     break 
            # else:
            #     count += 1

        print(
            f"END   = IOMem Range [{idx}] {x.start:<16x} {x.start + x.size:<16x} "
            f"{x.size/page_size} Pages "
        )

    with open(g2h_file, "w") as text_file:
        assert len(gpa2hpa) == len(gpa2hva)
        for idx in range(len(gpa2hpa)):
            print(
                f"gPA : 0x{gpa2hpa[idx][0]:<16x} --->"
                f" hVA: 0x{gpa2hva[idx][1]:<16x}"
                f" hPA: 0x{gpa2hpa[idx][1]:<16x} ",
                file=text_file,
            )
    print(f"{len(gpa2hva)} entries written to {g2h_file}")

    return gpa2hva, gpa2hpa
'''