# Benchmarking

The benchmarking script located at `/scripts/bench` builds and runs a series of images for benchmarking various CellulOS operations on the Odroid-C4 board.

## Setup 
(Assumes that `python 3.10` and `virtualenv` are already installed)

1. Create the virtualenv: `python -m venv venv`. 
2. Activate the virtualenv: `source ./venv/bin/activate`.
3. Install requirements: `pip install -r requirements.txt`.
    - If this doesn't work, these are the packages to install manually: 
    `setuptools sel4-deps protobuf grpcio-tools`.
4. Set configuration options in `run_benchmarks.py` (currently just hardcoded in the script).
    - Set the `build_folder` to the Odroid build folder in the OSmosis repo.

### Test Configuration
- Tests first need to be configured in `sel4test` using `sel4bench` to output timing results:
```c
static void print_result(uint64_t result)
{
    printf("RESULT>%lu\n", result);
}

int benchmark_something(env_t env)
{
    int error = 0;
    ccnt_t start, end;

    sel4bench_init();

    SEL4BENCH_READ_CCNT(start);
    // do X
    SEL4BENCH_READ_CCNT(end);
    print_result(end - start);

    SEL4BENCH_READ_CCNT(start);
    // do Y
    SEL4BENCH_READ_CCNT(end);
    print_result(end - start);

    sel4bench_destroy();
    return sel4test_get_result();
}

// For sel4utils test:
DEFINE_TEST_WITH_TYPE_MULTIPLE(GPIBM001, 
    "benchmark something", 
    benchmark_something,
    BASIC,
    true)

// OR, for osmosis test:
DEFINE_TEST_WITH_TYPE_MULTIPLE(GPIBM002, 
    "benchmark something", 
    benchmark_something,
    OSM,
    true)
```
- Then, add corresponding configuration(s) to the `run_benchmarks.py`
```python
test_configurations = [
    {
        "test_name": "GPIBM001",              # the test name from DEFINE_TEST
        "run_type": run_type_reboot,          # run the test with reboot
        "bench_names": ["X", "Y"],            # names of results, in print-order
        "system_type": system_type_sel4test,  # for sel4utils test
        "pd_deletion_depth": 0,               # cleanup policy setting
        "rs_deletion_depth": 0,               # cleanup policy setting
    },
    {
        "test_name": "GPIBM002",
        "run_type": run_type_reboot,                 
        "bench_names": ["X", "Y"],
        "system_type": system_type_osm,       # for osmosis test
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM001",
        "run_type": run_type_noreboot,        # run the test with no reboot
        "bench_names": ["X", "Y"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
]

selected_tests = test_configurations
```
- If the system type is `system_type_osm`, then the script will enable `GPIServerEnabled`, otherwise it will be disabled.

## Running Benchmarks
This makes the assumption that your environment is set up as described in [booting](target_booting_assumptions).
1. Choose which test configurations to run: in the script set, the `selected_tests` variable.
2. Set other configuration options:
    - Set the `n_iter_bits` to the adjust the number of iterations for each benchmark.
        - For tests where the board is not rebooted between every iteration, the number of reboots will 1, and the number of iterations per reboot will be `2^n_iter_bits`.
        - For tests where the board is rebooted between every iteration, the number of reboots will be `2^n_iter_bits`.
    - Choose print verbosity with the `print_uboot` / `print_sel4test` / `print_logs` options.
    - If you are rerunning benchmarks and the images to test are already built, you can set `rebuild = False` to save time.
3. From within the virtualenv: `sudo -E env PATH=$PATH python run_benchmarks.py`.
    - `sudo` is needed for the script to access `/dev/ttyUSB0` & `/dev/ttyUSB0`, and copy build images to `/srv/tftp`.
    - Alternatively, to run a process in the background that will not be killed when the ssh session closes: `bash ./run` (you may need to run a `sudo` command from this terminal session first). You can check on its progress using `cat nohup.out`.
    - To find your benchmark processes running in the background: `ps -ef | grep run_benchmarks.py`.
4. Results are saved to `benchmarks.csv`. 
    - The file is updated after every test type has finished all iterations, or if there is an error that causes the script to abort.