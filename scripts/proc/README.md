# Proc Model State

This is a sample script to extract model state from linux `/proc` (WIP)

## Setup
1. Create the virtualenv: `python -m venv venv`.
2. Activate the virtualenv: `source ./venv/bin/activate`.
3. Install requirements: `pip install -r requirements.txt`.
    - Or manually install packages: `psutil`.

## Run
1. Activate the virtualenv: `source ./venv/bin/activate`.
2. Run `sudo -E env PATH=./venv/bin python proc_model.py`.