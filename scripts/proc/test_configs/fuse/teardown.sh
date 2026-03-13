#!/usr/bin/env bash
# fuse/teardown.sh — kill FUSE server and client, unmount filesystem.
MOUNT=/tmp/osmosis-fuse-test/fusey-passthrough

# Kill all passthrough.py and hello processes started by setup.sh
pkill -f 'passthrough.py' 2>/dev/null || true
pkill -f '/proc/test_programs/hello' 2>/dev/null || true

# Unmount FUSE filesystem
sleep 0.5
fusermount -u "$MOUNT" 2>/dev/null || sudo umount -l "$MOUNT" 2>/dev/null || true

# Remove working directory
rm -rf /tmp/osmosis-fuse-test 2>/dev/null || true
