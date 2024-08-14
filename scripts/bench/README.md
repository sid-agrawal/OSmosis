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
#include <sel4gpi/bench_utils.h>

int benchmark_something(env_t env)
{
    BENCH_UTILS_PD_INIT;
    BENCH_UTILS_FN_INIT;

    BENCH_UTILS_START();
    // do X
    BENCH_UTILS_END("X");

    BENCH_UTILS_START();
    // do Y
    BENCH_UTILS_END("Y");

    BENCH_UTILS_DESTROY;
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
        "run_nanobench": False,               # don't enable nanobenchmarks in the GPI server
    },
    {
        "test_name": "GPIBM002",
        "run_type": run_type_reboot,                 
        "bench_names": ["X", "Y"],
        "system_type": system_type_osm,       # for osmosis test
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
        "run_nanobench": False,
    },
    {
        "test_name": "GPIBM001",
        "run_type": run_type_noreboot,        # run the test with no reboot
        "bench_names": ["X", "Y"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,        
        "run_nanobench": False,
    },
]

selected_tests = test_configurations
```
- If the system type is `system_type_osm`, then the script will enable `GPIServerEnabled`, otherwise it will be disabled.

#### Configuration for Nanobenchmarks
- Additionally, you can break down operations into "nano" benchmarks:
```c
#include <sel4gpi/bench_utils.h>

int do_X()
{
    BENCH_UTILS_FN_INIT;

    BENCH_UTILS_START();
    // do a
    BENCH_UTILS_END_NANO("a");

    BENCH_UTILS_START();
    // do b
    BENCH_UTILS_END_NANO("b");
}

int benchmark_something(env_t env)
{
    BENCH_UTILS_PD_INIT;
    BENCH_UTILS_FN_INIT;

    BENCH_UTILS_RECORD_NANO();
    BENCH_UTILS_START();
    // do X
    BENCH_UTILS_END("X");
    BENCH_UTILS_STOP_RECORD_NANO();

    BENCH_UTILS_DESTROY;
    return sel4test_get_result();
}

DEFINE_TEST_WITH_TYPE_MULTIPLE(GPIBM003, 
    "benchmark something", 
    benchmark_something,
    OSM,
    true)
```
- And add a corresponding configuration
```python
test_configurations = [
    {
        "test_name": "GPIBM003",
        "run_type": run_type_reboot,
        "bench_names": ["X_a", "X_b", "X"],     # Names of nano and regular results
        "system_type": system_type_osm,
        "pd_deletion_depth": 0, 
        "rs_deletion_depth": 0, 
        "run_nanobench": True,                  # Enable nanobenchmarks in the GPI server
    }
    // ...
]
```
- Note that the `run_nanobench` options is specifically for enabling nanobenchmark outputs in the GPI server. If you add nanobenchmark outputs elsewhere, they will not be affected by this parameter.
- The `BENCH_UTILS_RECORD_NANO` / `BENCH_UTILS_STOP_RECORD_NANO` macros print markers for the benchmark script, so it knows when to record nanobenchmark results. This way, we can ignore output for operations we don't want to track.

selected_tests = test_configurations
```
## Running Benchmarks
This makes the assumption that your environment is set up as described in [booting](target_booting_assumptions).
1. Choose which test configurations to run: in the script, set the `selected_tests` variable.
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