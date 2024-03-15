# CellulOS: An implementation of the OSmosis model.
The details of the OSmosis model are available [here](https://arxiv.org/abs/2309.09291)


## Setup the dev machine

Instructions copied verbatim from [sel4test](https://docs.sel4.systems/projects/sel4test/).

The basic build package on Ubuntu is the build-essential package. To install run:
```bash
sudo apt-get update
sudo apt-get install build-essential
```
Additional base dependencies for building seL4 projects on Ubuntu include installing:

```bash
sudo apt-get install cmake ccache ninja-build cmake-curses-gui
sudo apt-get install libxml2-utils ncurses-dev
sudo apt-get install curl git doxygen device-tree-compiler
sudo apt-get install u-boot-tools
sudo apt-get install python3-dev python3-pip python-is-python3
sudo apt-get install protobuf-compiler python3-protobuf
```
#### Simulating with QEMU

In order to run seL4 projects on a simulator you will need QEMU:
```bash
sudo apt-get install qemu-system-arm qemu-system-x86 qemu-system-misc
```

#### Cross-compiling for ARM targets
To build for ARM targets you will need a cross compiler:
```bash
sudo apt-get install gcc-arm-linux-gnueabi g++-arm-linux-gnueabi
sudo apt-get install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
# (you can install the hardware floating point versions as well if you wish)

sudo apt-get install gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf
```
## Setup a new workspace


```bash
# Clone OSmosis and all the submodules
git clone --recurse-submodules git@github.com:sid-agrawal/OSmosis.git
cd OSmosis
# Make sure that the cellulos branch is checked out
git submodule foreach git checkout cellulos
git status # This should show no chanages, as all the commits should be on the cellulos branch
```

## Build & Run
### Qemu
```bash
mkdir build
cd build
../init-build.sh -DAARCH64=TRUE  -DPLATFORM=qemu-arm-virt -DSIMULATION=TRUE -DDEBUG=TRUE
ninja
./simulate
```

### Odroid C4

```bash
mkdir build
cd build
 ../init-build.sh -DAARCH64=TRUE  -DPLATFORM=odroidc4 -DDEBUG=TRUE
ninja
# Look at notion for steps on how to copy the binary to the board via TFTP
```

### Running with SMP Enabled
#### Build Arguments
`../init-build.sh -DAARCH64=TRUE  -DPLATFORM=qemu-arm-virt -DSIMULATION=TRUE -DSMP=TRUE -DDEBUG=TRUE`
This will enable 4 cores by default, pass in `-DKernelMaxNumNodes=<CORES>` to change this

#### SMP with QEMU
1. If running on WSL, in the [config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) files, give it at least 8GB in RAM (otherwise tests won't run at all) and at least 4 virtual processors (otherwise it will run very slowly).
2. invoke `./simulate -m 8G`, with 8G as a minimum. QEMU is run with 4 cores by default, pass in `-smp <CORES>` to change this.

## Generate new compile commands
Compile commands file is used for code navigation. This workspace's
vscode settings file is configured to use it.

```bash
cd build
bear --output ../compile_commands.json -- ninja
```

## Typical workflow
Let's follow rules to make our lives easier:
* All the submodules are using a fork maintained by `sid-agrawal`.
* All `OSmosis` commits go the `celluos` branch for every module, including the parent OSmosis repo.
* Let's not push code to submodules that we do not reflect in OSmosis repo yet.
In other words let's keep them in sync.
   * Using `git push --recurse-submodules=on-demand` should make enforce this. More on this below.



### Commit your changes
TLDR; Commit and push individual sub-modules first, and then do the same in the parent repo.

Set up this alias once. This alias will get added to your repo-local `.git/config`

```bash
git config alias.supercommit '!./supercommit.sh "$@"; #'
```

| Note: This will add and commit everything, which may be you do not want sometimes.

Then to commit do:
```bash
git supercommit "some message"
```

```bash
cat ./supercommit.sh
#!/bin/bash -e
if [ -z "$1" ]; then
    echo "You need to provide a commit message"
    exit
fi

git submodule foreach "
    git add -A .
    git update-index --refresh
    commits=\$(git diff-index HEAD)
    if [ ! -z \"\$commits\" ]; then
        git commit -am \"$1\"
    fi"

git add -A .
git commit -am "$1"
```

### Push all changes
Read the `Publishing submodules` section [here](https://git-scm.com/book/en/v2/Git-Tools-Submodules).

It will push the files and the modules refs from OSmosis repo, and if it sees that a particular module ref
is not yet pushed, it will push that too.

```bash
git push --recurse-submodules=on-demand
```


### Bring in new changes

`I am fairly certain this should be okay, but we will see.`

```bash
# bring in new refs for submodules
git pull --rebase
# Update the code in the modules, if there is a conflict with local, this should complain.

# Then Resolve conflicts, supercommit
[...]
# Push
git push --recurse-submodules=on-demand
```




