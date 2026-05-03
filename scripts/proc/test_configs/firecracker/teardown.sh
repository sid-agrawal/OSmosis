#!/usr/bin/env bash
# teardown.sh — Kill any lingering Firecracker processes and clean up sockets.
pkill -f "firecracker --api-sock /tmp/osmosis-fc" 2>/dev/null || true
rm -f /tmp/osmosis-fc-app.sock /tmp/osmosis-fc-kvs.sock
