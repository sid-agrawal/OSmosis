#!/bin/python

import os
import pexpect
from utils import is_root

def get_cellulos_phandle(simulate_cmd: str):

    print(f"Running CMD: {simulate_cmd} in {os.getcwd()}")
    phandle = pexpect.spawn(simulate_cmd)
    phandle.expect("Booting Linux on physical CPU 0x0000000000", timeout=60)
    sim_output = phandle.before.decode()

    host_output = []
    for ln in sim_output.splitlines():
        if ln.startswith("NODE_TYPE") or \
             ln.startswith("PD") or \
               ln.startswith("RESOURCE") or \
                 ln.startswith(",,"): # Edges
                 host_output.append(ln)




    # search for the Name pattern.
    phandle.expect("buildroot login:", timeout=60)
    phandle.sendline("root")
    phandle.expect("#")


    # send the username with sendline
    phandle.sendline("cd /root/proc")
    phandle.expect("#")
    # phandle.sendline("\n\n")

    return phandle, host_output

def get_qemu_phandle(qemu_cmd: str) -> pexpect.spawn:

    phandle = pexpect.spawn("sudo " + qemu_cmd)

    # search for the Name pattern.
    phandle.expect("buildroot login:")
    phandle.sendline("root")
    phandle.expect("#")

    # send the username with sendline
    phandle.sendline("cd /root/proc")
    phandle.expect("#")
    # phandle.sendline("\n\n")

    return phandle

def main():
    """
    For now this only exercises get_qemu_phandle
    """

    username = os.getlogin()
    qemu_cmd = os.path.expanduser(
        "/home/" + username + "/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"
    )
    phandle = get_qemu_phandle(qemu_cmd)
    phandle.interact()

if __name__ == "__main__":
    assert is_root()
    main()
