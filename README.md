# CellulOS: An implementation of the OSmosis model.
The details of the OSmosis model are available [here](https://arxiv.org/abs/2309.09291)

## Running the project
Instructions to setup and run are the same as [sel4test](https://docs.sel4.systems/projects/sel4test/)


## Information on branches and submodules
This repo and all its submodules are working off the `cellulos` branch
and with a fork from `sid-agrawal`.


## Setup a new workspace
```bash
git clone --recursive git@github.com:sid-agrawal/OSmosis.git
cd OSmosis
```

## Build & Runt
```bash
mkdir build
../init-build.sh -DAARCH64=TRUE  -DPLATFORM=qemu-arm-virt -DSIMULATION=TRUE -DDEBUG=TRUE
ninja
./simulate
```

## Bring in new changes


