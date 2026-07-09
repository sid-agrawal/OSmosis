#!/bin/bash
# Run inside L1 (Debian arm64, EL2/KVM). Measures Linux-as-HV:
#  (1) VM boot phases of the identical 5.18 L2 guest, N iterations (KVM, cpu host).
#  (2) process creation inside L1 (fork+exec), via procbench.
# Emits CSV to results/.  Usage: ./run_linux_hv.sh [N_boot] [N_proc]
set -u
cd "$(dirname "$0")"
NB=${1:-5}
NP=${2:-300}
mkdir -p results
TS=$(date +%Y%m%d_%H%M%S)

BOOT_CSV="results/linux_hv_boot_${TS}.csv"
echo "iter,guest_entry_ms,userspace_ms,login_ms" > "$BOOT_CSV"
echo "== VM boot phases (KVM, cpu host), N=$NB =="
for i in $(seq "$NB"); do
    L="results/l2_kvm_${TS}_$i.log"
    expect boot_phases.exp linux rootfs.cpio.gz 512M 300 host kvm > "$L" 2>&1
    ge=$(grep -aoE "PHASE:guest_entry:[0-9]+" "$L" | head -1 | cut -d: -f3)
    us=$(grep -aoE "PHASE:userspace:[0-9]+"  "$L" | head -1 | cut -d: -f3)
    lo=$(grep -aoE "PHASE:login:[0-9]+"      "$L" | head -1 | cut -d: -f3)
    echo "$i,${ge:-NA},${us:-NA},${lo:-NA}" | tee -a "$BOOT_CSV"
done

echo "== process creation inside L1 (fork+exec), N=$NP =="
PROC_CSV="results/linux_hv_proc_${TS}.txt"
./procbench "$NP" ./trivial | grep -E "iterations|mean_ms" | tee "$PROC_CSV"

echo "== summary (boot phase means, ms) =="
awk -F, 'NR>1 && $2!="NA"{ge+=$2;us+=$3;lo+=$4;n++} END{if(n)printf "guest_entry=%.0f userspace=%.0f login=%.0f (N=%d)\n",ge/n,us/n,lo/n,n}' "$BOOT_CSV"
echo "done -> $BOOT_CSV , $PROC_CSV"
