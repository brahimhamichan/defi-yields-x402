#!/usr/bin/env python3
"""keeper-x402 v2: two-leg fused keeper (own x402 API + third-party Aave V3).

  LEG 1 (our API):  keeper.load_snapshot / keeper.evaluate (fixture in demo,
                    live-cache-mirror in live). Never pays, never mocked beyond
                    v1's own deterministic fixture.
  LEG 2 (Aave V3):  aave_read.read_aave_usdc() — ALWAYS a live eth_call on
                    Base. No mocks, no fixtures on this path, in any mode.

  FUSION (frozen policy, per-leg freshness — honest about stale legs):
    fresh_legs = legs whose data is fresh (API: keeper MAX_AGE_S gate;
                 Aave: block timestamp within AAVE_MAX_SKEW_S of read time)
    fused_apy = max APY over fresh legs; fire iff fused_apy >= THRESHOLD.
    A stale leg is reported with its numbers but excluded from the decision.

  Output: demo_output_v2.json (fused decision artifact) + audit_trail.jsonl
  record. The plan hash freezes {leg refs, decision, steps}.

Usage:
  python3 keeper_v2.py demo   # fixture API leg + LIVE Aave leg
  python3 keeper_v2.py live   # live-cache API leg + LIVE Aave leg
"""
import hashlib
import json
import os
import sys
import time

import aave_read
import keeper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "demo_output_v2.json")
THRESHOLD = keeper.THRESHOLD
AAVE_MAX_SKEW_S = 3600  # on-chain leg is fresh iff its block isato recent


def fuse(mode):
    t0 = keeper.now()
    snap, source = keeper.load_snapshot(mode)
    api_decision = keeper.evaluate(snap)
    api_age = keeper.snapshot_age_s(snap)
    api_fresh = api_age <= keeper.MAX_AGE_S
    api_top_apy = None
    pools = [p for p in snap.get("pools", [])
             if isinstance(p.get("apy"), (int, float))]
    if pools:
        top = max(pools, key=lambda p: p["apy"])
        api_top_apy = {"symbol": top["symbol"], "apy": top["apy"],
                       "project": top.get("project"), "chain": top.get("chain")}

    aave, rpc_url = aave_read.read_aave_usdc()  # always live; raises if down
    aave_skew = abs(time.time() - aave["block_timestamp"])
    aave_fresh = aave_skew <= AAVE_MAX_SKEW_S

    candidates = []
    if api_fresh and api_top_apy:
        candidates.append({"leg": "x402-api", "apy": api_top_apy["apy"],
                           "detail": api_top_apy})
    if aave_fresh:
        candidates.append({"leg": "aave-v3-base-usdc",
                           "apy": aave["supply_apy_pct"],
                           "detail": {"symbol": "USDC", "chain": "Base"}})
    winner = max(candidates, key=lambda c: c["apy"]) if candidates else None
    fire = bool(winner and winner["apy"] >= THRESHOLD)
    if winner:
        reason = ("threshold-met" if fire else "below-threshold") \
            + "-via-" + winner["leg"]
    else:
        reason = "no-fresh-legs"

    decision = {
        "fire": fire, "reason": reason, "threshold": THRESHOLD,
        "legs": {
            "x402_api": {"source": source,
                         "fetched_at": snap.get("fetched_at"),
                         "age_s": round(api_age), "fresh": api_fresh,
                         "top": api_top_apy,
                         "v1_verdict": api_decision["reason"]},
            "aave_v3": {"fresh": aave_fresh, "block_skew_s": round(aave_skew),
                        "read": aave},
        },
        "fused_apy": winner["apy"] if winner else None,
        "winning_leg": winner["leg"] if winner else None,
    }

    if not fire:
        steps = [{"seq": 1, "action": "notify",
                  "params": {"channel": "keeperhub-audit",
                             "message": "keeper-x402 v2 idle: %s "
                             "(api=%s, aave-usdc=%s%%)" % (
                                 reason, api_top_apy,
                                 aave["supply_apy_pct"])}}]
    else:
        w = winner["detail"]
        steps = [
            {"seq": 1, "action": "keeperhub.web3/check-balance",
             "params": {"network": "8453"}},
            {"seq": 2, "action": "keeperhub.condition.apy-gate",
             "params": {"venue": winner["leg"], "symbol": w["symbol"],
                        "apy_pct": winner["apy"], "threshold": THRESHOLD,
                        "operator": ">="}},
            {"seq": 3, "action": "keeperhub.notify.route",
             "params": {"channel": "audit",
                        "message": "route $100 -> %s %s @ %s%% (fused %s)" % (
                            winner["leg"], w["symbol"], winner["apy"],
                            reason)}}]
    body = json.dumps({"mode": mode, "api_fetched_at": snap.get("fetched_at"),
                       "aave_block": aave["block_number"],
                       "aave_liq_ray": aave["liquidity_rate_ray"],
                       "decision": decision, "steps": steps}, sort_keys=True)
    plan = {"steps": steps,
            "plan_hash": hashlib.sha256(body.encode()).hexdigest()[:16]}

    result = {"run_at": t0, "mode": mode, "keeper_version": "v2-two-leg",
              "policy": {"min_apy_pct": THRESHOLD,
                         "api_max_age_s": keeper.MAX_AGE_S,
                         "aave_max_skew_s": AAVE_MAX_SKEW_S},
              "decision": decision, "execution_plan": plan,
              "keeperhub_binding": "keeperhub_workflow.json (import or MCP "
                                   "create_workflow); v2 adds an Aave-read "
                                   "Code node before the Condition"}
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    keeper.audit({"ts": t0, "mode": mode, "keeper_version": "v2-two-leg",
                  "trigger": "%s + aave-v3@block-%d-via-%s"
                  % (source, aave["block_number"], rpc_url),
                  "simulation": {"wouldRevert": False,
                                 "decision": reason},
                  "plan_hash": plan["plan_hash"], "outcome": "planned",
                  "gas_used": "n/a (dry-run, nothing broadcast)"})
    print(json.dumps(result, indent=2))
    print("wrote %s and appended %s" % (OUT_JSON, keeper.AUDIT_LOG))
    return result


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("demo", "live") else "demo"
    fuse(mode)
