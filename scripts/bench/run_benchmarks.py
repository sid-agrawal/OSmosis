import serial
from time import sleep
import pandas as pd
import os.path as path
from subprocess import run
from os import chdir, getcwd
from shutil import copyfile

### CONFIGURATION ###

# Paths
build_folder = "/home/arya/OSmosis/odroid-build/"
tftboot_folder = "/srv/tftp/"
build_image_path = "./images/sel4test-driver-image-arm-odroidc4" # from the build folder

# Print options
print_uboot = False
print_sel4test = False

# CSV filename for output
csv_path = "./benchmarks.csv"

# Definitions for test configurations
system_type_sel4test = "sel4test"
system_type_osm = "osm"

basic_bench_names = ["PD create", "Frame create", "ADS create", "ADS attach", "CPU create", "CPU bind", \
                     "ADS remove", "Frame delete", "PD delete", "CPU delete", "ADS delete"]
spawn_bench_names = ["PD Spawn", "Send cap", "IPC to PD"]
fs_bench_names = ["File Create"]
cleanup_toy_block_server_names = ["PD cleanup toy block server"]
cleanup_toy_file_server_names = ["PD cleanup toy file server"]
cleanup_toy_db_server_names = ["PD cleanup toy db server"]
cleanup_ramdisk_names = ["PD cleanup ramdisk"]
cleanup_fs_names = ["PD cleanup fs"]

# Test configurations
n_iters = 50 # Number of iterations for reboot tests

ipc_test_configurations = [
    {
        "test_name": "GPIBM010",
        "n_reboots": n_iters,
        "bench_names": ["Regular IPC to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM011",
        "n_reboots": n_iters,
        "bench_names": ["NanoPB to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM010",
        "n_reboots": 1,
        "bench_names": ["Regular IPC to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM011",
        "n_reboots": 1,
        "bench_names": ["NanoPB to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM012",
        "n_reboots": 1,
        "bench_names": ["Repeated IPC to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM013",
        "n_reboots": 1,
        "bench_names": ["Repeated NanoPB to RT"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
]

basic_test_configurations = [
    {
        "test_name": "GPIBM001",
        "n_reboots": n_iters,
        "bench_names": basic_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    }, 
    {
        "test_name": "GPIBM001",
        "n_reboots": 1,
        "bench_names": basic_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM003",
        "n_reboots": n_iters,
        "bench_names": spawn_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    }, 
    {
        "test_name": "GPIBM003",
        "n_reboots": 1,
        "bench_names": spawn_bench_names,
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM002",
        "n_reboots": n_iters,
        "bench_names": basic_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    }, 
    {
        "test_name": "GPIBM002",
        "n_reboots": 1,
        "bench_names": basic_bench_names,
        "system_type": system_type_osm,
    },
    {
        "test_name": "GPIBM004",
        "n_reboots": n_iters,
        "bench_names": spawn_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    }, 
    {
        "test_name": "GPIBM004",
        "n_reboots": 1,
        "bench_names": spawn_bench_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
]

toy_cleanup_test_configurations = [
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 2,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 2,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM006",
        "n_reboots": 1,
        "bench_names": cleanup_toy_block_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 3,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM007",
        "n_reboots": 1,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM007",
        "n_reboots": 1,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
    },
    {
        "test_name": "GPIBM007",
        "n_reboots": 1,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM007",
        "n_reboots": 1,
        "bench_names": cleanup_toy_file_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM008",
        "n_reboots": 1,
        "bench_names": cleanup_toy_db_server_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
]

cleanup_test_configurations = [
    {
        "test_name": "GPIBM0014",
        "n_reboots": n_iters,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM0014",
        "n_reboots": n_iters,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 1,
    },
    {
        "test_name": "GPIBM0014",
        "n_reboots": n_iters,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM0014",
        "n_reboots": n_iters,
        "bench_names": cleanup_ramdisk_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 2,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM0015",
        "n_reboots": n_iters,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM0015",
        "n_reboots": n_iters,
        "bench_names": cleanup_fs_names,
        "system_type": system_type_osm,
        "pd_deletion_depth": 1,
        "rs_deletion_depth": 0,
    },
]
selected_tests = ipc_test_configurations

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
tests_finished = b'All is well in the universe\r\n'
test_result = "RESULT>"

# Commands
off_command_bytes = bytearray([0xa0, 0x01, 0x00, 0xa1])
on_command_bytes = bytearray([0xa0, 0x01, 0x01, 0xa2])

def image_name_from_config(config):
    """
    Generate an image name for a test configuration
    """
    return (
        f'{config["test_name"]}'
        f'-{config["system_type"]}'
        f'-{"reboot" if config["n_reboots"] > 1 else "noreboot"}'
        f'-{config["pd_deletion_depth"]}'
        f'-{config["rs_deletion_depth"]}'
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
        print("../init-build.sh", 
             "-DPLATFORM=odroidc4", 
             f'-DLibSel4TestPrinterRegex={config["test_name"]}',
             f'-DGPIServerEnabled={"ON" if config["system_type"] == system_type_osm else "OFF"}',
             f'-DGPIBenchmarkMultiple={"ON" if config["n_reboots"] == 1 else "OFF"}',
             f'-DGPIPDDeletionDepth={config["pd_deletion_depth"]}',
             f'-DGPIRSDeletionDepth={config["rs_deletion_depth"]}')
        
        run(["../init-build.sh", 
             "-DPLATFORM=odroidc4", 
             f'-DLibSel4TestPrinterRegex={config["test_name"]}',
             f'-DGPIServerEnabled={"ON" if config["system_type"] == system_type_osm else "OFF"}',
             f'-DGPIBenchmarkMultiple={"ON" if config["n_reboots"] == 1 else "OFF"}',
             f'-DGPIPDDeletionDepth={config["pd_deletion_depth"]}',
             f'-DGPIRSDeletionDepth={config["rs_deletion_depth"]}'])
        
        # Build the image
        run(["ninja"])
        
        # Copy the image
        image_name = image_name_from_config(config)
        dest_path = path.join(tftboot_folder, image_name)
        copyfile(build_image_path, dest_path)
        
    # Return to previous dir
    chdir(cwd)
        
    
def power_off(uart_device):
    """
    Send a message to power off the board
    """
    
    print("Powering off")
    uart_device.write(off_command_bytes)
    sleep(1)
    uart_device.write(off_command_bytes)

def power_on(uart_device):
    """
    Send a message to power on the board
    """
    
    print("Powering on")
    uart_device.write(on_command_bytes)
    sleep(1)
    uart_device.write(on_command_bytes)

def boot(serial_device, config):
    """
    Call after power_on
    Receives serial output from the uboot image on the board
    Sends a tftpboot command to load the desired image
    """
    
    print("Booting odroid with uboot...")

    line = ""
    image_name = image_name_from_config(config)

    while (line != uboot_input):
        line = serial_device.readline()

        if print_uboot:
            print(line.decode(), end='')

        if (len(line) == 0):
            print("Timeout while reading from serial")
            return
    
    print("Loading image...")
    serial_device.write(str.encode(f'tftpboot 0x20000000 {lindt_ip}:{image_name}; go 0x20000000\n'))

    while (line != uboot_starting):
        line = serial_device.readline()

        if print_uboot:
            print(line.decode(), end='')

        if (len(line) == 0):
            print("Timeout while reading from serial")
            return
    
    print("Running sel4...")

def read_result(serial_device, n_columns):
    """
    Reads the serial output from the sel4 image
    Saves benchmark results to an array of dimension (n_results, n_columns)
    - n_columns is given
    - n_results is the number of results read from terminal divided by n_columns
    """
    line = ""
    results = []    # total results of this boot
    row_idx = 0     # current result row
    column_idx = 0  # current result column

    while (line != tests_finished):
        line = serial_device.readline()

        # Uncomment this line to see running messages
        if print_sel4test:
            print(line.decode(), end='')
        
        line_str = line.decode()

        if len(line) == 0:
            print("Timeout while reading from serial")
            return results
        elif line_str.startswith(test_result):
            # Start a new row if needed
            if column_idx == 0:
                results.append([])

            # Append the result
            results[row_idx].append(int(line_str[len(test_result):]))

            # Increment the column
            column_idx += 1

            # Check if the row is finished
            if column_idx == n_columns:
                row_idx += 1
                column_idx = 0

    return results

if __name__ == "__main__":
    # Build the images
    build_images(build_folder, selected_tests)
     
    # Run the Benchmarks
    df = pd.DataFrame()
    uart_device = serial.Serial(uart_device_name, timeout=3)
    power_off(uart_device)

    for test_config in selected_tests:
        print("")
        print("Running test: ", test_config["test_name"], "-",
              test_config["system_type"], "-",
              "reboot" if test_config["n_reboots"] > 1 else "no reboot")
        
        results = []
        
        for i in range(test_config["n_reboots"]):
            # New serial connection
            serial_device = serial.Serial(serial_device_name, baudrate=115200, timeout=10)

            # Boot
            power_on(uart_device)
            boot(serial_device, test_config)
            result = read_result(serial_device, len(test_config["bench_names"]))

            if (len(result) == 0):
                print(f'Failed cycle {i}')

            # Store result and shutdown
            results.extend(result)
            power_off(uart_device)
            serial_device.close()

        # Update the CSV
        columns = [(f'{x}'
                    f' - {test_config["system_type"]}'
                    f' - {"reboot" if test_config["n_reboots"] > 1 else "no reboot"}'
                    f' - [{test_config["pd_deletion_depth"]}, {test_config["rs_deletion_depth"]}]') 
                   for x in test_config["bench_names"]]
        df_new = pd.DataFrame.from_records(results, columns=columns)

        # Combine new data with old data
        df = pd.merge(df, df_new, how="outer", left_index=True, right_index=True)

    uart_device.close()
    df.to_csv(csv_path, header=True, index=False)

    