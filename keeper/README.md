# keeper-x402 — KeeperHub-triggered keeper over our live x402 DeFi API

A deterministic keeper loop: our live pay-per-call DeFi API
(`https://devbox.tail08c9f0.ts.net`, $0.01 USDC/call on Base) is the data
trigger; a frozen policy decides; the exact execution plan KeeperHub would run
is emitted with a hash; every run is audit-logged. Nothing is inferred at
execution time — the plan *is* the run.

## How to run (no keys, no spend, stdlib only)

```bash
cd /home/brahim/code/money-goal/keeper
./demo.sh                 # demo (fixture) + live (probes real paywall, $0)
# or individually:
python3 keeper.py demo    # offline-safe fixture run
python3 keeper.py live    # live 402-paywall check + real cache snapshot
APY_THRESHOLD=8.0 python3 keeper.py live   # stricter policy
```

Artifacts produced: `demo_output.json` (full run result), `demo.log`
(both runs), `audit_trail.jsonl` (KeeperHub-style audit records).

## Files (183 lines of code total)

| File | What |
|---|---|
| `keeper.py` (172) | trigger → condition → frozen plan → audit; `demo`/`live` modes |
| `keeperhub_workflow.json` | the same loop as a KeeperHub workflow (Schedule → Code/x402 → Condition → web3 check → notify) |
| `demo.sh` (10) | runs both modes, saves `demo.log` |

## How it maps to the judging rubric

1. **Integration depth** — the trigger is a real, named live project: our own
   x402 DeFi API (4 paid endpoints, live 402 quotes on Base, verified in-run).
2. **Execution through KeeperHub** — `keeperhub_workflow.json` uses real node
   types from the KeeperHub docs (`Schedule` trigger, `code/run`, `Condition`
   with `sourceHandle: true/false`, `web3/check-balance` on `8453`); the paid
   x402 fetch maps to KeeperHub's agentic-wallet + x402 story. Final broadcast
   needs a human `kh_` key (boss step) — everything up to it runs here.
3. **Reliability & observability** — stale-snapshot gate, below-threshold idle
   path, never-500 fallbacks, JSONL audit trail with plan hash per run.
4. **Usefulness & originality** — turns a pay-per-call data API into an
   autonomous yield-routing keeper: the agent economy's data leg + execution
   leg in one loop.
5. **DX & code quality** — stdlib only, 183 lines, one-command demo,
   deterministic fixture + live modes.

## v2 — two-leg fused keeper (own x402 API + third-party Aave V3 on Base)

v1's weakness ("our own API as the live project") is fixed: v2 fuses our
API snapshot with a **live third-party protocol read** — Aave V3
`Pool.getReserveData(USDC)` on Base (`0xA238…d1c5`) via free public RPC,
no keys, no spend. One net-APY decision artifact, frozen plan hash.

```bash
./demo_v2.sh                 # decoder selftest + demo + live, spends $0
# or individually:
python3 aave_read.py selftest   # deterministic decoder unit check (offline)
python3 aave_read.py            # raw live Aave read
python3 keeper_v2.py demo       # fixture API leg + LIVE Aave leg
python3 keeper_v2.py live       # live-cache API leg + LIVE Aave leg
```

New files (v1 files untouched): `aave_read.py` (live Base RPC reader +
decoder), `keeper_v2.py` (per-leg-freshness fusion → fused artifact),
`demo_v2.sh`. New artifacts: `demo_output_v2.json` (live run),
`demo_output_v2_fire.json` (live run, `APY_THRESHOLD=3.0`, proves the fire
branch end-to-end), `demo_v2.log`. Observed live 2026-09-11: Aave V3 Base
USDC supply **3.7366%**, borrow 4.6564%, utilization ~0.80, block 51152004
(skew 1s); stale API leg (7.03% @ 3 days old) honestly excluded from fusion.

## Re-scored rubric mapping (v2, honest)

1. **Integration depth** — improved (was weakest): third-party leg added
   (Aave V3, live `eth_call`, decoded + sanity-checked against known aToken
   `0x4e65…0ab`). Own-API leg retained as leg 1.
2. **Execution through KeeperHub** — improved slightly: full fire branch
   proven live (`threshold-met-via-aave-v3-base-usdc`, plan `b8d47255…`);
   broadcast still needs the human `kh_` key (unchanged).
3. **Reliability & observability** — improved: per-leg freshness (stale legs
   excluded, never silently trusted), 3-RPC failover, both branches
   audit-logged with plan hashes.
4. **Usefulness & originality** — improved: cross-venue net-APY routing
   (own index vs on-chain truth) instead of single-source routing.
5. **DX & code quality** — held: stdlib only, same one-command demo pattern.

## What still needs the human (at submit time, not now)

- KeeperHub account + `kh_` org key → import `keeperhub_workflow.json`
  (or MCP `create_workflow`) and run once on Base Sepolia.
- That run's tx link + a screen-record of `./demo.sh` + the workflow run
  = the 3 submission artifacts.
