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

## Generate new compile commands
Compile commands file is used for code navigation. This workspace's
vscode settings file is configured to use it.

```bash
cd build
bear --output ../compile_commands.json -- ninja
```

## Typical workflow
Some rules to make our lives easier.
| Let's not push code to submodules that we do not reflect in OSmosis repo yet.
In other words let's keep them in sync.



### Commit your changes
TLDR; Commit and push individual sub-modules first, and then do the same in the parent repo.

Just once set up this alias, which will get added to your repo local `.git/config`
```bash
git config alias.supercommit '!./supercommit.sh "$@"; #'
```

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

### Bring in new changes

`I am unsure if this is the right way, we will see.`

```bash
# bring in new refs for submodules
git pull --rebase
git submodule update --rebase
[Resolve conflicts, commit in individuals as needed]
git submodule foreach git push origin cellulos
```



