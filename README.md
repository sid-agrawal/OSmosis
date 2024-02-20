# CellulOS: An implementation of the OSmosis model.
The details of the OSmosis model are available [here](https://arxiv.org/abs/2309.09291)

## Running the project
Instructions to setup and run are the same as [sel4test](https://docs.sel4.systems/projects/sel4test/)


## Information on branches and submodules
This repo and all its submodules are working off the `cellulos` branch
and with a fork from `sid-agrawal`.


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
git submodule update --rebase
# Then Resolve conflicts, supercommit
[...]
# Push
git push --recurse-submodules=on-demand
```




