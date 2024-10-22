#!/bin/python3

import pexpect
import subprocess
import os
import telnetlib
import traceback
from proc_model import extract_process_data, ProcFsData, MappingType

username = os.getlogin()
qemu_cmd = "sudo /home/"+username+"/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"
 

host = "localhost"
port = 45454

def get_qemu_monitor_state():
    telnet_cmd = "telnet localhost 45454"
    gpa2hpa_cmd = "gpa2hpa 0x0100000"
    child = pexpect.spawn(telnet_cmd)
    child.expect("(qemu)")

    child.sendline(gpa2hpa_cmd)
    child.expect("(qemu)")
    print(child.before.decode())

def get_vm_state():
 
    # spawn a child process.
    child = pexpect.spawn(qemu_cmd)
    print("CHILD PID: ", child.pid)
 
    # search for the Name pattern.
    child.expect("buildroot login:")
    child.sendline('root')
    child.expect("#")
 
    # send the username with sendline
    child.sendline('cd /root/proc')
    child.expect("#")
    
    child.sendline('python proc_model.py --csv ./hello.csv')
    child.expect("#")
    
    child.sendline('cat ./hello.csv')
    child.expect("#")

    print(child.before.decode())

    get_host_state(child.pid)
    get_qemu_monitor_state()


    # print the interactions with the child 
    # process.
    # child.interact()



def main():
    get_vm_state()


def get_host_state(vm_pid: int):
    # # Create a copy of the current environment variables
    # custom_env = os.environ.copy()
    # # Modify the PATH environment variable
    
    # # Define the command to be executed
    # command = [ "python", "proc_model.py", "--pid", str(vm_pid), "--csv", "tmp.output"]
    
    # # Execute the command
    # process = subprocess.Popen(command, env=custom_env)
    # # Wait for the process to complete
    # process.wait()

    data = ProcFsData()
    try:
        extract_process_data(data, vm_pid, "qemu", True)
    except Exception as e:
        print("Error printing stats for QEMU")
        print(repr(e))
        traceback.print_exc()
        exit (1)

    data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS).to_csv("tmp.csv")

if __name__ == "__main__":
    main()