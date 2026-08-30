# Real-system case study

Scripts for the case study in Chapter 6 of the dissertation: running IsoSearch on an
OSmosis graph extracted from a live Linux machine.

## Getting the graph

The graph is not checked in (150 MB). Regenerate it with Lintool:

    cd <OSmosis>/scripts/proc
    sudo -E python3 proc_model.py --os linux \
        --pids "$(for p in $(ls /proc | grep -E '^[0-9]+$'); do \
                    [ -r /proc/$p/cmdline ] && \
                    [ -n "$(tr -d '\0' < /proc/$p/cmdline 2>/dev/null | head -c 1)" ] && \
                    echo $p; done | paste -sd,)" \
        --csv /tmp/linux_user.csv

`--pid 0` (whole machine) does not work: kernel threads have no address space, so the
per-process `pagemap` read fails and extraction aborts on the first one. The command above
passes only user-space PIDs.

The graph depends on what the machine was running, so numbers will not match the
dissertation exactly. Ours had 159 PDs, 494,112 resources and 1,710,359 edges.

## Running the search

    python3 explore_linux2.py --beam 12 --depth 10

- `load_real.py`  loads a Lintool CSV into the graph shape IsoSearch consumes
- `scoped.py`     restricts the graph to one cgroup cohort
- `privspace.py`  a transition that swaps a shared resource-space for a private one,
                  which the standard transition set cannot express
- `containerize.py` a synthetic scaling scenario used for the alpha/beta sensitivity check

`privatize_space` is registered for this scenario only, not added to `PRIMITIVES`, so the
case studies in `scenarios.py` are unaffected.
