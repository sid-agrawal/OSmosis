#!/usr/bin/env bash
# setup.sh — Two standalone Firecracker VMM processes (no VM boot needed).
# Firecracker processes wait on API sockets; we capture their PIDs for proc extraction.
# No container runtime wraps these processes — they run in host namespaces directly.
set -euo pipefail

if ! command -v firecracker &>/dev/null; then
    echo "SKIP=firecracker not installed" >&2
    exit 1
fi
if [ ! -e /dev/kvm ]; then
    echo "SKIP=/dev/kvm not available" >&2
    exit 1
fi

# Clean up stale sockets from a previous run
rm -f /tmp/osmosis-fc-app.sock /tmp/osmosis-fc-kvs.sock

# Start two FC processes waiting on API sockets (no VM configured — processes just wait).
# Redirect all FDs to /dev/null so the background processes don't inherit the capture
# pipes from subprocess.run(), which would prevent the pipes from closing on exit.
firecracker --api-sock /tmp/osmosis-fc-app.sock </dev/null >/dev/null 2>&1 &
APP_PID=$!
firecracker --api-sock /tmp/osmosis-fc-kvs.sock </dev/null >/dev/null 2>&1 &
KVS_PID=$!

# Brief pause to ensure both processes appear in /proc
sleep 1

# Validate processes are still running
if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "ERROR: osmosis-fc-app firecracker process exited unexpectedly" >&2
    exit 1
fi
if ! kill -0 "$KVS_PID" 2>/dev/null; then
    echo "ERROR: osmosis-fc-kvs firecracker process exited unexpectedly" >&2
    kill "$APP_PID" 2>/dev/null || true
    exit 1
fi

echo "APP_PID=$APP_PID"
echo "KVS_PID=$KVS_PID"
