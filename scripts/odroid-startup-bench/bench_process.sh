#!/usr/bin/env bash
# Measure hello world process startup time: 50 warm + 10 cold runs.
# Run from the odroid-startup-bench/ directory after: gcc -O2 -static -o hello hello.c
set -euo pipefail

N_WARM=${N_WARM:-50}
N_COLD=${N_COLD:-10}
OUTFILE="results/process_$(date +%Y%m%d_%H%M%S).csv"
mkdir -p results

if [ ! -x ./hello ]; then
    echo "Building hello (static)..."
    gcc -O2 -static -o hello hello.c
fi

echo "run,mode,seconds" > "$OUTFILE"

parse_time() {
    # Extract real time from bash `time` output (format: Xm Y.YYYs)
    awk '/real/{print $2}' | sed 's/m/:/; s/s//' | \
        awk -F: '{printf "%.6f\n", $1*60+$2}'
}

echo "=== Warm runs (${N_WARM}) ==="
for i in $(seq "$N_WARM"); do
    t=$( { time ./hello > /dev/null; } 2>&1 | parse_time )
    echo "$i,warm,$t" >> "$OUTFILE"
    printf "\r  run %d/%d  %.3f ms" "$i" "$N_WARM" "$(echo "$t * 1000" | bc -l)"
done
echo ""

echo "=== Cold runs (${N_COLD}, dropping page cache each time) ==="
for i in $(seq "$N_COLD"); do
    sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
    t=$( { time ./hello > /dev/null; } 2>&1 | parse_time )
    echo "$i,cold,$t" >> "$OUTFILE"
    printf "\r  run %d/%d  %.3f ms" "$i" "$N_COLD" "$(echo "$t * 1000" | bc -l)"
done
echo ""

echo ""
echo "=== Summary (ms) ==="
awk -F, 'NR>1 {
    sum[$2]+=$3; sum2[$2]+=$3*$3; cnt[$2]++
} END {
    for (m in sum) {
        mean = sum[m]/cnt[m]
        var  = sum2[m]/cnt[m] - mean*mean
        sd   = (var>0) ? sqrt(var) : 0
        printf "%s: mean=%.3f ms  stddev=%.3f ms  n=%d\n", m, mean*1000, sd*1000, cnt[m]
    }
}' "$OUTFILE"

echo ""
echo "Results: $OUTFILE"
