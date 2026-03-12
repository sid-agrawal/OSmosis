#!/usr/bin/env bash
# proc_model.py already kills containers via terminate_process; this is a safety net
docker rm -f osmosis-kata-app osmosis-kata-kvs 2>/dev/null || true
