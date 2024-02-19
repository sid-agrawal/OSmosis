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
git submodule foreach git checkout cellulos
```

## Build & Run
```bash
mkdir build
../init-build.sh -DAARCH64=TRUE  -DPLATFORM=qemu-arm-virt -DSIMULATION=TRUE -DDEBUG=TRUE
ninja
./simulate
```

## Typical workflow
Some rules to make our lives easier
* Let's not push code to submodules that we do not reflect in OSmosis repo yet.
In other words let's keep them in sync.


`I am unsure if this is the right way`

### Commit your changes
```bash
[Code Code Code]
git submodule foreach git add .
git submodule foreach git commit -m "good description"
```
###
Bring in new changes
```bash
git submodule foreach git pull --rebase
[Resolve conflicts, commit in individuals as needed]
git submodule foreach git push origin cellulos

# Now update refs in OSmosis
git add .
git commit -m "update refs in OSmosis"
git push
```




