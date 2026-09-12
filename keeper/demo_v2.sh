#!/usr/bin/env bash
# keeper-x402 v2 demo: decoder selftest + two-leg fused run. No keys, no spend.
set -u
cd "$(dirname "$0")"
echo "=== 1/3 aave decoder selftest (deterministic, offline) ==="
python3 aave_read.py selftest | tee demo_v2.log
echo "=== 2/3 v2 demo (fixture API leg + LIVE Aave V3 leg) ==="
python3 keeper_v2.py demo | tee -a demo_v2.log
echo "=== 3/3 v2 live (live-cache API leg + LIVE Aave V3 leg) ==="
python3 keeper_v2.py live | tee -a demo_v2.log
echo "=== artifacts: demo_output_v2.json (live run), demo_v2.log, audit_trail.jsonl ==="
ls -la demo_output_v2.json demo_v2.log audit_trail.jsonl
