#!/usr/bin/env bash
# keeper-x402 demo: deterministic dry-run + live paywall probe. No keys, no spend.
set -u
cd "$(dirname "$0")"
echo "=== 1/2 demo (fixture, fully offline-safe) ==="
python3 keeper.py demo | tee demo.log
echo "=== 2/2 live (probes live 402 paywall + real cache, spends \$0) ==="
python3 keeper.py live | tee -a demo.log
echo "=== artifacts: demo_output.json (live run), audit_trail.jsonl ==="
ls -la demo_output.json audit_trail.jsonl
