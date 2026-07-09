#!/usr/bin/env bash
# Measure QEMU VM boot time (time to BusyBox shell prompt).
# Run from odroid-startup-bench/ after running build_initrd.sh.
# Requires: qemu-system-aarch64 expect
set -euo pipefail

N=${N:-10}
OUTFILE="results/vm_$(date +%Y%m%d_%H%M%S).csv"
mkdir -p results

for f in vmlinuz initrd.img; do
    [ -f "$f" ] || { echo "ERROR: $f not found. Run build_initrd.sh first."; exit 1; }
done
command -v expect >/dev/null || { echo "ERROR: expect not installed. Run: sudo apt install expect"; exit 1; }

echo "run,mode,seconds" > "$OUTFILE"

run_qemu() {
    local mode=$1 kvm_flag=$2 run=$3
    # Use expect to detect the BusyBox shell prompt and measure wall time.
    # t_start is captured in bash; expect sends it to the spawned process env
    # and reports elapsed ms via stderr.
    local elapsed
    elapsed=$(
        T_START=$(date +%s%N)
        expect -c "
            set t_start [expr {[clock milliseconds]}]
            spawn qemu-system-aarch64 -M virt -cpu host ${kvm_flag} -m 128M \
                -kernel vmlinuz -initrd initrd.img \
                -append {console=ttyAMA0 quiet} -nographic
            expect {
                {/ #} {
                    set elapsed [expr {[clock milliseconds] - \$t_start}]
                    puts stderr \"ELAPSED:\$elapsed\"
                    send {poweroff\r}
                    expect eof
                }
                timeout {
                    puts stderr \"ELAPSED:TIMEOUT\"
                    exit 1
                }
            }
        " 2>&1 | grep ELAPSED | sed 's/ELAPSED://'
    )
    if [ "$elapsed" = "TIMEOUT" ]; then
        echo "  run $run TIMEOUT" >&2
        return 1
    fi
    local secs
    secs=$(awk "BEGIN {printf \"%.3f\", $elapsed/1000}")
    echo "$run,$mode,$secs" >> "$OUTFILE"
    printf "  run %d/%d  %.2f s\n" "$run" "$N" "$secs"
}

if [ -e /dev/kvm ]; then
    echo "=== KVM mode (${N} runs) ==="
    for i in $(seq "$N"); do run_qemu kvm "-enable-kvm" "$i" || true; done
else
    echo "WARNING: /dev/kvm not found — skipping KVM mode (kernel 4.9 may lack KVM support)"
fi

echo "=== TCG software emulation mode (${N} runs) ==="
for i in $(seq "$N"); do run_qemu tcg "" "$i" || true; done

echo ""
echo "=== Summary ==="
awk -F, 'NR>1 {
    sum[$2]+=$3; sum2[$2]+=$3*$3; cnt[$2]++
} END {
    for (m in sum) {
        mean = sum[m]/cnt[m]
        var  = sum2[m]/cnt[m] - mean*mean
        sd   = (var>0) ? sqrt(var) : 0
        printf "%s: mean=%.2f s  stddev=%.2f s  n=%d\n", m, mean, sd, cnt[m]
    }
}' "$OUTFILE"

echo ""
echo "Results: $OUTFILE"
