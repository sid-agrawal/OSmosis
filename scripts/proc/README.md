# Proc Model State

This is a sample script to extract model state from linux `/proc`

## Setup
1. Create the virtualenv: `python -m venv venv`.
2. Activate the virtualenv: `source ./venv/bin/activate`.
3. Install requirements: `pip install -r requirements.txt`.
    - Or manually install packages: `pybind11`, `networkx`.
4. Build the `pfs` module: `pfs` is a c++ library, so we use a `pybind` wrapper to generate a Python module from it.
    - Enter the `pfs` directory: `cd pfs`.
    - Build: `cmake . & make`.
    - This should generate a python module: `/pfs/lib/pypfs.[...].so`.

## Run
1. Activate the virtualenv: `source ./venv/bin/activate`.
2. Run `sudo -E env PATH=./venv/bin python proc_model.py`.

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