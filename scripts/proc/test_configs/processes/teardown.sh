#!/usr/bin/env bash
# teardown.sh — Kill all hello processes started by setup.sh.
pkill -x hello 2>/dev/null || true
