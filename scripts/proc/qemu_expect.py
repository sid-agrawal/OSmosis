#!/bin/python

import os
import pexpect
from utils import is_root

def get_qemu_phandle(qemu_cmd: str) -> pexpect.spawn:

    phandle = pexpect.spawn("sudo " + qemu_cmd)
    print("CHILD PID: ", phandle.pid)

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

    username = os.getlogin()
    qemu_cmd = os.path.expanduser(
        "/home/" + username + "/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"
    )
    phandle = get_qemu_phandle(qemu_cmd)
    phandle.interact()

if __name__ == "__main__":
    assert is_root()
    main()
