## Benchmarking

This script builds and runs a series of images for benchmarking CellulOS on the Odroid-C4 board.

### Setup 
(Assumes that `python 3.10` and `virtualenv` are already installed)

1. Create the virtualenv: `python -m venv venv` 
2. Activate the virtualenv: `source ./venv/bin/activate`
3. Install requirements: `pip install -r requirements.txt`
    - If this doesn't work, these are the packages I installed manually: 
    `setuptools sel4-deps protobuf grpcio-tools`
4. Set configuration options in `run_benchmarks.py` (currently just hardcoded in the script)
    - Set the `build_folder` to a folder in the OSmosis repo

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
DEFINE_TEST(GPIBM001, "benchmark something", benchmark_something, true)

// OR, for osmosis test:
DEFINE_TEST_OSM(GPIBM002, "benchmark something", benchmark_something, true)

// OR, to run the test many times in one boot:
DEFINE_TEST_WITH_TYPE_MULTIPLE(GPIBM003, 
    "benchmark something", 
    benchmark_something,
    BASIC, // BASIC for sel4utils test, OSM for osmosis test
    true)
```
- Then, add corresponding configuration(s) to the `run_benchmarks.py`
```python
test_configurations = [
    {
        "test_name": "GPIBM001",              # the test name from DEFINE_TEST
        "n_reboots": n_iters,                 # number of reboots
        "bench_names": ["X", "Y"],            # names of results, in print-order
        "system_type": system_type_sel4test,  # for sel4utils test
        "pd_deletion_depth": 0,               # cleanup policy setting
        "rs_deletion_depth": 0,               # cleanup policy setting
    },
    {
        "test_name": "GPIBM002",
        "n_reboots": n_iters,                 
        "bench_names": ["X", "Y"],
        "system_type": system_type_osm,       # for osmosis test
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
    {
        "test_name": "GPIBM003",
        "n_reboots": 1,                        # n_reboots is 1 when running the test
                                               # many times in one boot
        "bench_names": ["X", "Y"],
        "system_type": system_type_sel4test,
        "pd_deletion_depth": 0,
        "rs_deletion_depth": 0,
    },
]

selected_tests = test_configurations
```

### Running Benchmarks
1. Choose which test configurations to run: in the script set, the `selected_tests` variable
2. From within the virtualenv: `sudo -E env PATH=$PATH python run_benchmarks.py`
    - `sudo` is needed for the script to access `/dev/ttyUSB0` & `/dev/ttyUSB0`, and copy build images to `/srv/tftp`
    - Alternatively, to run a process in the background that will not be killed when the ssh session closes: `bash ./run`
3. Results are saved to `benchmarks.csv`