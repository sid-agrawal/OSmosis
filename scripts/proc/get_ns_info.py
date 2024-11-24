import os
import fcntl
import sys
import argparse

# See: https://man7.org/linux/man-sudo pages/man2/NS_GET_USERNS.2const.html
# Constants for ioctl operations
NS_GET_USERNS = 0xb701
NS_GET_PARENT = 0xb702
NS_GET_NSTYPE = 0xb703

NESTABLE_NS_TYPES = ["pid", "user"]

def get_ns_ID_from_fd(fd):
    """
        For fd of a NS, the NS_ID is stored in the file's inode number.

        The 
    """
    if fd == -1:
        return fd
    stat_buf = os.fstat(fd)
    return stat_buf.st_ino

def ioctl_wrapper(fd: int, op:int) -> int:
    """
        Convert error into a return value of -1
    """
    try:
        rv_fd = fcntl.ioctl(fd, op)
    except PermissionError:
        print(f"Permission denied for ioctl operation {op} on fd {fd}", file=sys.stderr)
        rv_fd = -1
    return rv_fd

def getNSInfo(pid: int, ns_type: str) -> list[str]:

    """"
        Give a PID (in the host's PID NS), and NS_Type (user or PID),
        get the NS_ID that the PID is operating in and the parent NS_ID.
    """

    assert ns_type in NESTABLE_NS_TYPES

    # This can be any NS's file, but since we plan to use PID ns in one of the cases,
    # we just open that.
    pathname = f"/proc/{pid}/ns/pid"
    ns_fd = os.open(pathname, os.O_RDONLY)

    match ns_type:
        case "pid":
            # Perform ioctl operation, to get the parent NS's fd.
            parent_ns_fd = ioctl_wrapper(ns_fd, NS_GET_PARENT)
        case "user":
            # A separate ioctl is needed to get the fd to the current processes USER NS_ID.
            ns_fd = ioctl_wrapper(ns_fd, NS_GET_USERNS)
            # Perform ioctl operation, to get the parent NS's fd.
            parent_ns_fd = ioctl_wrapper(ns_fd, NS_GET_PARENT)
        case _:
            raise ValueError ("Invalid NS Type")

    rv = [
        get_ns_ID_from_fd(ns_fd), 
        get_ns_ID_from_fd(parent_ns_fd), 
            ]

    # Close the files if they were opened.
    if ns_fd != -1: 
        os.close(ns_fd)
    if parent_ns_fd != -1: 
        os.close(parent_ns_fd)
    return rv

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Print the handle of the NS and its parent"
    )
    parser.add_argument(
        "-p",
        "--pid", type=int, help="PID of the process to extract data for"
    )
    parser.add_argument(
        "-n",
        "--ns-type", type=str, required=True, choices=NESTABLE_NS_TYPES
    )
    args = parser.parse_args()
    ns_ID, parent_ns_ID = getNSInfo(args.pid, args.ns_type)
    
    print(f"For PID: {args.pid} and NS_Type {args.ns_type}")
    print(f"Current: {ns_ID} Parent: {parent_ns_ID}")