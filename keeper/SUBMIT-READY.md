# SUBMIT-READY — keeper-x402 (KeeperHub: The Agent Economy Hackathon)

## Title

**keeper-x402: a KeeperHub keeper that routes on live x402 DeFi data**

## 3-sentence pitch

Our live x402 pay-per-call DeFi API ($0.01 USDC/call on Base) is the trigger;
a frozen APY policy decides; KeeperHub is the deterministic execution layer
that runs the exact plan — no reinterpretation at execution time. The keeper
polls every 30 min, buys the yields snapshot via x402, and only fires the
balance-check + route-alert branch when top stable APY ≥ 5%. Every run emits
a hashed execution plan plus an audit-trail record, so judges can verify
trigger, decision, and outcome independently.

## Repo path

`/home/brahim/code/money-goal/keeper/` → push as-is (files: `keeper.py`,
`keeperhub_workflow.json`, `demo.sh`, `README.md`, this file, plus committed
`demo.log`, `demo_output.json`, `audit_trail.jsonl`).

## Demo link / artifact

- [ ] Screen-record `./demo.sh` + KeeperHub workflow run → upload (unlisted) → paste URL here at submit time.
- Committed local proof (already in dir): `demo.log`, `demo_output.json`, `audit_trail.jsonl`.

## Track

**Main track: Best Integration into a Live Project** ($4,000 pool; 1st $2,000 / 2nd $1,200 / 3rd $800).
Integrated project: our live x402 DeFi API at `https://devbox.tail08c9f0.ts.net`
(deployed product, live 402 quotes — not a wrapper: the keeper consumes its
real snapshots and verifies its paywall in-run).
Bounty (separate BUIDL, optional later): package the x402-fetch Code node as a
KeeperHub connector/PR — stacks with main track.

## Eligibility answers (draft for the form)

- Integrated project + what it does: our x402 DeFi API (pay-per-call yields/
  signals/bridge-fees/router on Base); the keeper buys its data and routes on it.
- KeeperHub surfaces used: workflow builder (Schedule trigger, Code action,
  Condition, web3 action), MCP `create_workflow`/`execute_workflow`, x402
  (agentic wallet pays the $0.01 data call), audit trail.
- Testnet or mainnet: dry-run + Base Sepolia preflight first; mainnet Base for
  the final judged tx (KeeperHub gas sponsorship if available).
- What still breaks / is unfinished: final on-chain broadcast awaits the
  human `kh_` key + one funded run; all logic up to broadcast is proven
  (`demo.log`, plan hashes `e49e478b…` demo / `b9414a53…` live 2026-09-08).
- Contact: boss fills (email + X/Discord).

## Pre-submit checklist

- [x] Working code, runs with zero secrets/spend (`./demo.sh` green 2026-09-08)
- [x] Workflow definition matches real KeeperHub node types (per docs)
- [x] Demo artifacts committed in dir
- [ ] Boss: register on DoraHacks (human email) + KeeperHub account/`kh_` key
- [ ] Import workflow, run once → capture tx link
- [ ] Record demo video → create bounty-BUIDL + main-BUIDL (one BUIDL per track)
- [ ] Submit before **Sep 18, 12:00 CEST** (10:00 UTC)

## v2 package notes (appended 2026-09-11 — new files only, v1 untouched)

- What changed: third-party leg added — live Aave V3 `getReserveData(USDC)`
  read on Base via free public RPC, fused with our-API snapshot into one
  net-APY decision artifact with per-leg freshness + frozen plan hash
  (`keeper_v2.py`, `aave_read.py`, `demo_v2.sh`).
- New demo artifacts: `demo_output_v2.json` (live idle run, plan `d492896c…`),
  `demo_output_v2_fire.json` (live fire-branch run @ `APY_THRESHOLD=3.0`,
  plan `b8d47255…`), `demo_v2.log` (selftest + both runs), plus new
  `v2-two-leg` records in `audit_trail.jsonl`.
- Live proof observed: Aave V3 Base USDC supply 3.7366%, block 51152004
  (skew 1s); stale 7.03% API leg excluded from fusion — judges can re-run
  `./demo_v2.sh` ($0, no keys) to reproduce.
- Track/pitch unchanged (main track); v2 answers the "own API as the live
  project" review note. Human list unchanged (DoraHacks + `kh_` key + tx +
  video).
