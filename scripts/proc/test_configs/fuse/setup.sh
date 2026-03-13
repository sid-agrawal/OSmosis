#!/usr/bin/env bash
# fuse/setup.sh — start a FUSE passthrough server and a client hello process.
# Uses external-PID mode so conftest.py extracts them (not proc_model --config 7).
set -euo pipefail

WORKDIR=/tmp/osmosis-fuse-test
PYBIN=/home/siagraw/proc/pyenv/bin/python
PASSTHROUGH=/home/siagraw/proc/test_programs/passthrough.py
HELLO=/home/siagraw/proc/test_programs/hello
MOUNT="$WORKDIR/fusey-passthrough"

# Clean up any leftover state
fusermount -u "$MOUNT" 2>/dev/null || sudo umount -l "$MOUNT" 2>/dev/null || true
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

# Start FUSE server in background from the workdir (passthrough.py uses relative paths)
cd "$WORKDIR"
nohup "$PYBIN" "$PASSTHROUGH" >"$WORKDIR/server.log" 2>&1 &
SERVER_PID=$!

# Wait for FUSE mount to be ready (up to 10 s)
for i in $(seq 1 20); do
    if mount | grep -q "$MOUNT"; then
        break
    fi
    sleep 0.5
done

if ! mount | grep -q "$MOUNT"; then
    echo "ERROR: FUSE mount not ready after 10s" >&2
    kill "$SERVER_PID" 2>/dev/null || true
    exit 1
fi

# Start a hello client process (same MNT namespace → sees the FUSE mount in mountinfo)
nohup "$HELLO" >/dev/null 2>&1 &
CLIENT_PID=$!

sleep 0.5

echo "APP_PID=$SERVER_PID"
echo "KVS_PID=$CLIENT_PID"
