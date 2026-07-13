#!/usr/bin/env bash
# setup.sh — Two standalone Firecracker microVMs, each actually booted.
#
# This scenario used to start two `firecracker --api-sock ...` processes and never
# configure a VM ("no VM boot needed"). An idle Firecracker waiting on its API socket has
# NOT opened /dev/kvm: it opens the device when the VM is created. So the old scenario
# measured two idle VMM processes, and vm_boundary only came out true because the process
# happened to be *named* "firecracker". Now that vm_boundary is a structural test (a HOLD
# edge to /dev/kvm; see graph_queries._holds_vm_device) the VM has to be real.
#
# Each VM boots a kernel and its own rootfs over the API socket, so each process genuinely
# holds /dev/kvm. No container runtime wraps them: they run in the host namespaces
# directly, which is the point of the scenario (a VM boundary and nothing else).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES="$HERE/images"
KERNEL="$IMAGES/vmlinux"
ROOTFS_SRC="$IMAGES/rootfs.ext4"

if ! command -v firecracker &>/dev/null; then
    echo "SKIP=firecracker not installed" >&2
    exit 1
fi
if [ ! -e /dev/kvm ]; then
    echo "SKIP=/dev/kvm not available" >&2
    exit 1
fi
if [ ! -f "$KERNEL" ] || [ ! -f "$ROOTFS_SRC" ]; then
    echo "SKIP=firecracker guest images missing; see $IMAGES/README.md" >&2
    exit 1
fi

boot_vm() {
    # $1 = name, $2 = api socket, $3 = private rootfs copy
    local name=$1 sock=$2 rootfs=$3
    rm -f "$sock"
    # Each VM gets its own writable rootfs, so the two guests share no block device.
    cp --reflink=auto "$ROOTFS_SRC" "$rootfs"

    firecracker --api-sock "$sock" </dev/null >/dev/null 2>&1 &
    local pid=$!

    for _ in $(seq 1 50); do
        [ -S "$sock" ] && break
        sleep 0.1
    done
    if [ ! -S "$sock" ]; then
        echo "ERROR: $name never created its API socket" >&2
        kill "$pid" 2>/dev/null || true
        return 1
    fi

    curl -fsS --unix-socket "$sock" -X PUT 'http://localhost/boot-source' \
        -H 'Content-Type: application/json' \
        -d "{\"kernel_image_path\":\"$KERNEL\",\"boot_args\":\"console=ttyS0 reboot=k panic=1 pci=off\"}" >/dev/null

    curl -fsS --unix-socket "$sock" -X PUT 'http://localhost/drives/rootfs' \
        -H 'Content-Type: application/json' \
        -d "{\"drive_id\":\"rootfs\",\"path_on_host\":\"$rootfs\",\"is_root_device\":true,\"is_read_only\":false}" >/dev/null

    # InstanceStart is what makes Firecracker open /dev/kvm and create the VM.
    curl -fsS --unix-socket "$sock" -X PUT 'http://localhost/actions' \
        -H 'Content-Type: application/json' \
        -d '{"action_type":"InstanceStart"}' >/dev/null

    echo "$pid"
}

APP_PID=$(boot_vm osmosis-fc-app /tmp/osmosis-fc-app.sock /tmp/osmosis-fc-app.ext4)
KVS_PID=$(boot_vm osmosis-fc-kvs /tmp/osmosis-fc-kvs.sock /tmp/osmosis-fc-kvs.ext4)

# Let the guests come up and the VM fds settle.
sleep 2

for pair in "osmosis-fc-app:$APP_PID" "osmosis-fc-kvs:$KVS_PID"; do
    name=${pair%%:*}; pid=${pair##*:}
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "ERROR: $name exited unexpectedly" >&2
        kill "$APP_PID" "$KVS_PID" 2>/dev/null || true
        exit 1
    fi
    # The whole point of the scenario: the VMM must really hold the virtualization device.
    if ! ls -l "/proc/$pid/fd" 2>/dev/null | grep -q '/dev/kvm'; then
        echo "ERROR: $name (pid $pid) started but holds no /dev/kvm fd" >&2
        kill "$APP_PID" "$KVS_PID" 2>/dev/null || true
        exit 1
    fi
done

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
