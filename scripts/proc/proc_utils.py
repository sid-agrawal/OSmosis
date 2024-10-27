import os
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