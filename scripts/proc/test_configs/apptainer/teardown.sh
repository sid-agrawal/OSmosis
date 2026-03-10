#!/usr/bin/env bash
apptainer instance stop osmosis-app 2>/dev/null || true
apptainer instance stop osmosis-kvs  2>/dev/null || true
