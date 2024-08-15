import serial
import os
from time import sleep
import pandas as pd
import os.path as path
from subprocess import run
from os import chdir, getcwd
from shutil import copyfile
from sys import stdout
import re

### CONFIGURATION ###

# Paths
username = os.getlogin()
build_folder = "/home/"+username+"/OSmosis/odroid-build/"
tftboot_folder = "/srv/tftp/"
build_image_path = "./images/sel4test-driver-image-arm-odroidc4" # from the build folder

# Options
rebuild = True               # Rebuild the images
track_nano_benchmarks = True # If true, record benchmark points part of larger ops

# Print options
print_uboot = False         # Print the uboot logs
print_sel4test = True      # Print the sel4test output
print_logs = True           # Print logs from the benchmark script

# CSV filename for output
csv_path = "./benchmarks.csv"

# Definitions for test configurations
run_type_reboot = "reboot"
run_type_noreboot = "no_reboot"

system_type_sel4test = "sel4test"
system_type_osm = "osm"

basic_bench_names = ["PD create", "Frame create", "ADS create", "ADS attach", "CPU create", "CPU bind", \
                     "ADS remove", "Frame delete", "PD delete", "CPU delete", "ADS delete"]
spawn_bench_names = ["PD Spawn", "Send cap", "IPC to PD"]
fs_bench_names = ["File Create"]
cleanup_toy_block_server_names = ["PD cleanup toy block server"]
cleanup_toy_block_server_nano_names = ["Stop CPU", "Dec CPU", "Dec ADS", "Destroy CNode", "Destroy Notif", "Free ELF", "Cleanup Hold Registry", "Mark Linked PDs", "Free Init Data MO", "Free VKA", "Sweep Resource Spaces", "Sweep PDs", "Cleanup PD resource", "Clear Pending Work"]
cleanup_toy_file_server_names = ["PD cleanup toy file server"]
cleanup_toy_db_server_names = ["PD cleanup toy db server"]
cleanup_ramdisk_names = ["PD cleanup ramdisk"]
cleanup_fs_names = ["PD cleanup fs"]
cleanup_kvstore_names = ["PD cleanup kvstore"]

# Test configurations
n_iter_bits = 6          # Number of iterations for tests is 2^n_iter_bits
max_n_boot_retries = 5   # Number of times to try retry if serial is not working, before we abort the script

ipc_test_configurations = [
    {
        "test_name": "GPIBM100",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM101",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM102",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM103",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM104",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC 1 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM105",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC 1 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM106",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap 1 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM107",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap 1 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM108",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC 2 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM109",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC 2 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM110",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap 2 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM111",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap 2 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM112",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM113",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM114",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Cap Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM115",
        "run_type": run_type_noreboot,
        "bench_names": ["Regular IPC Cap Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM116",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC 1 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM117",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC 1 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM118",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Cap 1 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM119",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Cap 1 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM120",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Cap 2 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM121",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC 2 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM122",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC 2 Unwrapped Short"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM123",
        "run_type": run_type_noreboot,
        "bench_names": ["NanoPB IPC Cap 2 Unwrapped Long"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
]

basic_test_configurations = [
    {
        "test_name": "GPIBM001",
        "run_type": run_type_reboot,
        "bench_names": basic_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM001",
        "run_type": run_type_noreboot,
        "bench_names": basic_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM003",
        "run_type": run_type_reboot,
        "bench_names": spawn_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM003",
        "run_type": run_type_noreboot,
        "bench_names": spawn_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM002",
        "run_type": run_type_reboot,
        "bench_names": basic_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        
    }, 
    {
        "test_name": "GPIBM002",
        "run_type": run_type_noreboot,
        "bench_names": basic_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM004",
        "run_type": run_type_reboot,
        "bench_names": spawn_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM004",
        "run_type": run_type_noreboot,
        "bench_names": spawn_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
]

# The tests used in this config are:
#   - GPIBM006 "osm toy server cleanup, crash block server",
#   - GPIBM007 "osm toy server cleanup, crash file server",
#   - GPIBM008 "osm toy server cleanup, crash db server",
toy_cleanup_test_configurations = [
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_nano_names + cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": True,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 2,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 2,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM006",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 3,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM007",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM007",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM007",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM007",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM008",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_toy_db_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
]

cleanup_test_configurations = [
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 2,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 2,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM009",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 3,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM010",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM010",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM010",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM010",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM011",
        "run_type": run_type_noreboot,
        "bench_names": cleanup_kvstore_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
]

selected_tests = toy_cleanup_test_configurations[1:2]

# Configuration for tftpboot
lindt_ip = "10.42.0.1"

### CONSTANTS ###

# Devices
usb0 = '/dev/ttyUSB0'
usb1 = '/dev/ttyUSB1'
uart_device_name = usb0   # UART for power-cycle
serial_device_name = usb1 # Serial converter

# Output lines
uboot_input = b'=> '
uboot_starting = b'## Starting application at 0x20000000 ...\r\n'
test_finished_re = r'Test GPI.* passed'
tests_finished = b'All is well in the universe\r\n'
test_result = "RESULT>"
record_nano_start = ">STARTNANO"
record_nano_stop = ">STOPNANO"
nano_test_result = "NANORESULT>"
fail_assertion = "Assertion failed:"
fail_test = "        Error: result == SUCCESS"
fail_test_2 = "        Failure: result == SUCCESS"
fail_abort = "seL4 root server abort()ed"
fail_panic = "PANIC:"
fail_messages = [fail_assertion, fail_test, fail_test_2, fail_abort, fail_panic]

# Commands
off_command_bytes = bytearray([0xa0, 0x01, 0x00, 0xa1])
on_command_bytes = bytearray([0xa0, 0x01, 0x01, 0xa2])

# Exceptions
class BootTimeout(Exception):
    pass

class TestTimeout(Exception):
    pass

class TestFailure(Exception):
    pass

def log(*args):
    if print_logs:
        print(*args)
        
def image_name_from_config(config):
    """
    Generate an image name for a test configuration
    """
    return (
        f'{config["test_name"]}'
        f'-{config["system_type"]}'
        f'-{config["run_type"]}'
        f'-{config["pd_deletion_depth"]}'
        f'-{config["rs_deletion_depth"]}'
        f'{"-nano" if config["run_nanobench"] else ""}'
    )
    
def build_images(build_folder, configurations):
    """
    Build the images for the enabled tests
    - build_folder: A folder in the OSmosis repo to build odroid images
    - configurations: The selected test configurations to build images for
    """
    
    # Enter the build folder
    cwd = getcwd()
    chdir(build_folder)
    
    for config in configurations:
        # Configure the cmake options
        log("../init-build.sh", 
             "-DPLATFORM=odroidc4", 
             f'-DLibSel4TestPrinterRegex={config["test_name"]}',
             f'-DGPIServerEnabled={"ON" if config["system_type"] == system_type_osm else "OFF"}',
             f'-DGPINanobenchEnabled={"ON" if config["run_nanobench"] else "OFF"}',
             f'-DGPIBenchmarkIterBits={n_iter_bits if config["run_type"] == run_type_noreboot else 0}',
             f'-DGPIPDDeletionDepth={config["pd_deletion_depth"]}',
             f'-DGPIRSDeletionDepth={config["rs_deletion_depth"]}')
        
        run(["../init-build.sh", 
             "-DPLATFORM=odroidc4", 
             f'-DLibSel4TestPrinterRegex={config["test_name"]}',
             f'-DGPIServerEnabled={"ON" if config["system_type"] == system_type_osm else "OFF"}',
             f'-DGPINanobenchEnabled={"ON" if config["run_nanobench"] else "OFF"}',
             f'-DGPIBenchmarkIterBits={n_iter_bits if config["run_type"] == run_type_noreboot else 0}',
             f'-DGPIPDDeletionDepth={config["pd_deletion_depth"]}',
             f'-DGPIRSDeletionDepth={config["rs_deletion_depth"]}'])
        
        # Build the image
        run(["ninja"])
        
        # Copy the image
        image_name = image_name_from_config(config)
        dest_path = path.join(tftboot_folder, image_name)
        copyfile(build_image_path, dest_path)
        
        log(f"Wrote image to {dest_path}")
        
    # Return to previous dir
    chdir(cwd)
        
    
def power_off(uart_device):
    """
    Send a message to power off the board
    """
    
    log("Powering off")
    uart_device.write(off_command_bytes)
    sleep(1)
    uart_device.write(off_command_bytes)

def power_on(uart_device):
    """
    Send a message to power on the board
    """
    
    log("Powering on")
    uart_device.write(on_command_bytes)
    sleep(1)
    uart_device.write(on_command_bytes)

def boot(serial_device, config):
    """
    Call after power_on
    Receives serial output from the uboot image on the board
    Sends a tftpboot command to load the desired image
    """
    
    log("Booting odroid with uboot...")

    line = ""
    image_name = image_name_from_config(config)

    while (line != uboot_input):
        line = serial_device.readline()

        if print_uboot:
            print(line.decode(), end='')

        if (len(line) == 0):
            raise BootTimeout("Timeout while reading from serial")
    
    log(f"Loading image {image_name}...")
    serial_device.write(str.encode(f'tftpboot 0x20000000 {lindt_ip}:{image_name}; go 0x20000000\n'))

    while (line != uboot_starting):
        line = serial_device.readline()

        if print_uboot:
            print(line.decode(), end='')

        if (len(line) == 0):
            raise BootTimeout("Timeout while reading from serial")
    
    log("Running sel4...")

def read_single_test(serial_device, n_columns):
    """
    Reads the serial output from the sel4 image
    
    :param serial.Serial serial_device: The initialized serial device to read test output from
    :param int n_columns: The expected number of columns in one row of test results
    :param list[list[int]] results: Array to write results to
    :raises TestFailure: if the output indicates any test failed
    :raises TestTimeout: if there is a timeout while reading from serial
    
    Saves benchmark results to an array of dimension (1, n_columns)
    - n_columns is given
    """
    
    result = []
    line_str = ""              
    column_idx = 0             # current result column
    recording_nano = False
    
    while not re.match(test_finished_re, line_str):
        line = serial_device.readline()

        if print_sel4test:
            print(line.decode(), end='')
        
        line_str = line.decode()

        if len(line) == 0:
            raise TestTimeout("Timeout while reading from serial")
        
        elif line_str.startswith(record_nano_start):
            recording_nano = True
        
        elif line_str.startswith(record_nano_stop):
            recording_nano = False
            
        elif column_idx < n_columns and line_str.startswith(test_result):
            # Append the result
            result.append(int(line_str[len(test_result):]))

            # Increment the column
            column_idx += 1
        
        elif recording_nano and column_idx < n_columns and line_str.startswith(nano_test_result):
            # Append the result
            result.append(int(line_str[len(nano_test_result):]))

            # Increment the column
            column_idx += 1
        
        elif any([line_str.startswith(fail_msg) for fail_msg in fail_messages]):
            # Test failed for some reason
            raise TestFailure(f"Test failed with message: {line_str}")
    
    return result

def read_result(serial_device, n_columns, n_results, results):
    """
    Reads the serial output from the sel4 image
    
    :param serial.Serial serial_device: The initialized serial device to read test output from
    :param int n_columns: The expected number of columns in one row of test results
    :param int n_results: The expected number of test results to read
    :param list[list[int]] results: Array to write results to
    :raises TestFailure: if the output indicates any test failed
    :raises TestTimeout: if there is a timeout while reading from serial
    
    Saves benchmark results to an array of dimension (n_results, n_columns)
    - n_columns is given
    - n_results is the number of results read from terminal divided by n_columns
    """

    for _ in range(n_results):
        # Read one row
        results.append(read_single_test(serial_device, n_columns))
    
    # Wait for tests to finish
    line = ""
    while(line != tests_finished):
        line = serial_device.readline()

        if print_sel4test:
            print(line.decode(), end='')

if __name__ == "__main__":
    # Build the images
    if rebuild:
        build_images(build_folder, selected_tests)
    
    # Run the Benchmarks
    uart_device = serial.Serial(uart_device_name, timeout=3)
    power_off(uart_device)
    first_run = True

    for test_config in selected_tests:
        print("")
        print("Running test: ", test_config["test_name"], "-",
              test_config["system_type"], "-",
              test_config["run_type"])
        
        results = []
        
        i = 0
        n_boot_retries = 0
        n_reboots = 1 if test_config["run_type"] == run_type_noreboot else pow(2,n_iter_bits)
        n_results_per_boot = 1 if test_config["run_type"] == run_type_reboot else pow(2,n_iter_bits)
        while i < n_reboots:
            try:
                log(f"--> Begin Iteration {i}")
                
                # New serial connection
                serial_device = serial.Serial(serial_device_name, baudrate=115200, timeout=10)

                # Boot
                power_on(uart_device)
                boot(serial_device, test_config)
                read_result(serial_device, len(test_config["bench_names"]), n_results_per_boot, results)

                # Shutdown
                power_off(uart_device)
                serial_device.close()
                
                # Flush output for nohup
                stdout.flush()

                i += 1
                n_boot_retries = 0
            except BootTimeout:
                # Something went wrong while booting, try to recover
                print(f'Boot timeout for cycle {i}')
                
                if (n_boot_retries >= max_n_boot_retries):
                    print(f'Max number of retries reached, abort')
                    break
                
                power_off(uart_device)
                sleep(2)
                uart_device.close()
                
                uart_device = serial.Serial(uart_device_name, timeout=3)
                power_off(uart_device)
                sleep(2)
                
                n_boot_retries += 1
            except TestFailure as e:
                print(f'Test failure for cycle {i}, abort')
                print(e)
                break
            except TestTimeout:
                print(f'Test timeout for cycle {i}, abort')
                break
            except Exception as e:
                print(f'Unknown error for cycle {i}, abort')
                print(e)
                break
            
        # Read the old CSV
        if not first_run:
            df = pd.read_csv(csv_path, header=0)
        else:
            df = pd.DataFrame()
            first_run = False

        # Update the CSV
        columns = [(f'{x}'
                    f' - {test_config["system_type"]}'
                    f' - {test_config["run_type"]}'
                    f' - [{test_config["pd_deletion_depth"]}, {test_config["rs_deletion_depth"]}]') 
                   for x in test_config["bench_names"]]
        df_new = pd.DataFrame.from_records(results, columns=columns)

        # Combine new data with old data
        df = pd.merge(df, df_new, how="outer", left_index=True, right_index=True)
        
        # Save to file
        df.to_csv(csv_path, header=True, index=False)
        
        # Clear df from memory
        # This means we don't need to keep the entire csv in memory for long runs
        del df
        df = None
        
        # Quit if we reached the maximum number of retries
        if (n_boot_retries >= max_n_boot_retries):
            break

    uart_device.close()
