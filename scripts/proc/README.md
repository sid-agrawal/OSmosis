# Proc Model State

This is a sample script to extract model state from linux `/proc`

## Setup
1. Create the virtualenv: `python -m venv venv`.
2. Activate the virtualenv: `source ./venv/bin/activate`.
3. Install requirements: `pip install -r requirements.txt`.
    - Or manually install packages: `pybind11`, `networkx`.
4. Build the `pfs` module: `pfs` is a c++ library, so we use a `pybind` wrapper to generate a Python module from it.
    - Enter the `pfs` directory: `cd pfs`.
    - Build: `cmake .` then `make`.
    - This should generate a python module: `/pfs/lib/pypfs.[...].so`.

## Run
1. In `proc_model.py`, choose the configuration of programs to run.
    - You can choose an existing configuration by setting `to_run = run_configs[<idx>]` with the index of the chosen configuration.
    - To add a new configuration and/or programs, ensure that the programs are built by the makefile, and add them to the `program_names` and `run_configs` variables.
2. Activate the virtualenv: `source ./venv/bin/activate`.
3. Run `sudo -E env PATH=./venv/bin python proc_model.py`.
4. The resulting model state is saved to the `proc_model.csv` file, which can be imported into neo4j for visualization following the steps in `/scripts/model_state`.

---

## Investigation into procfs tools
We investigated some potential tools to use for getting information out of procfs, and the details are recorded here.
    
Python tools
- General: 
    - [proc library](https://pypi.org/project/proc/): Seems to be broken, for example it isn't getting the virtual address of virtual memory regions from `/proc/pid/maps`.
    - [procfs library](https://pypi.org/project/procfs/): I could not get this to run.
    - [psutil library](https://pypi.org/project/psutil/): Doesn't provide enough information for us.
    - [procpy library](https://code.google.com/archive/p/procpy/): Also not enough information.
    - [jc library](https://kellyjonbrazil.github.io/jc/docs/parsers/proc.html): Plain parser for all proc files, converts the file to a dict.
        - This one is useful, and we originally used it for `/maps` and `/smaps`. It did not have the ability to parse `/pagemap`, namespaces, and others.
    - [PyProc project](https://github.com/cnamejj/PyProc): Also intended to be a general parser.
        - It is for python 2, I used the [2to3](https://docs.python.org/3/library/2to3.html) package to convert it.
        - It is not set up to use easily as a module, and I did not think it was providing anything new, so I did not investigate further.
- Specific: 
    - [hazelnut library](https://github.com/barnumbirr/hazelnut) for `meminfo`: Just aggregated stats, not that useful to us.
     
Non-python tools:
- C++: https://github.com/dtrugman/pfs
    - This project seems the most active and well-rounded. We chose to use `PyBind` to access this library.
- Go: https://pkg.go.dev/github.com/prometheus/procfs#section-readme