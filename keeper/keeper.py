#!/usr/bin/env python3
"""keeper-x402: KeeperHub-triggered keeper over our live x402 DeFi API.

Deterministic loop (no inference at execution time):
  TRIGGER   snapshot yields (live cache mirror of our x402 API, paywall verified)
  CONDITION frozen policy: top stable APY >= THRESHOLD and snapshot fresh
  ACTION    emit frozen execution plan (exact steps KeeperHub would run) + hash
  AUDIT     append JSONL record mirroring KeeperHub audit-trail fields

No secrets, no spending, no accounts. Paid /yields is never called without
payment; we prove the paywall is live via its free 402 quote instead.
KeeperHub broadcast needs a human `kh_` key at submit time (see README) —
this prototype proves everything up to that broadcast deterministically.

Usage:
  python3 keeper.py demo   # offline-safe fixture -> demo_output.json + audit
  python3 keeper.py live   # probe live paywall + real cache, still spends $0
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API_BASE = os.environ.get("X402_API", "https://devbox.tail08c9f0.ts.net")
CACHE = "/home/brahim/code/money-goal/x402-api/yields_cache.json"
THRESHOLD = float(os.environ.get("APY_THRESHOLD", "5.0"))
MAX_AGE_S = 48 * 3600  # snapshot freshness gate
OUT_JSON = os.path.join(HERE, "demo_output.json")
AUDIT_LOG = os.path.join(HERE, "audit_trail.jsonl")

FIXTURE = {"endpoint": "/yields", "fetched_at": "2026-09-08T00:00:00Z",
           "count": 3, "pools": [
               {"pool": "fix-1", "chain": "Base", "project": "aave-v3",
                "symbol": "USDC", "tvlUsd": 1_000_000, "apy": 6.2,
                "apyBase": 5.2, "apyReward": 1.0},
               {"pool": "fix-2", "chain": "Ethereum", "project": "compound-v3",
                "symbol": "USDC", "tvlUsd": 2_000_000, "apy": 4.1,
                "apyBase": 4.1, "apyReward": 0.0},
               {"pool": "fix-3", "chain": "Arbitrum", "project": "aave-v3",
                "symbol": "USDT", "tvlUsd": 500_000, "apy": 3.0,
                "apyBase": 3.0, "apyReward": 0.0}]}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def snapshot_age_s(snap):
    try:
        ts = time.mktime(time.strptime(snap["fetched_at"], "%Y-%m-%dT%H:%M:%SZ"))
        return time.time() - ts
    except Exception:
        return float("inf")


def load_snapshot(mode):
    """TRIGGER: fixture (demo) or live cache mirror (live). Never pays."""
    if mode == "demo":
        return dict(FIXTURE), "fixture"
    try:
        with open(CACHE) as f:
            c = json.load(f)
        if isinstance(c, dict) and c.get("pools"):
            return c, "live-cache-mirror"
    except Exception as e:
        print("WARN: cache unreadable (%r), falling back to fixture" % e)
    return dict(FIXTURE), "fixture-fallback"


def probe_paywall():
    """Verify the live x402 paywall answers 402 (free). Returns (ok, detail)."""
    url = API_BASE + "/yields"
    req = urllib.request.Request(url, headers={"User-Agent": "keeper-x402/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return False, "unexpected HTTP %s (expected 402)" % r.status
    except urllib.error.HTTPError as e:
        if e.code != 402:
            return False, "unexpected HTTP %s (expected 402)" % e.code
        try:
            q = json.loads(e.read().decode("utf-8", "replace"))
            acc = (q.get("accepts") or [{}])[0]
            ok = (acc.get("asset") == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
                  and acc.get("amount") == "10000"
                  and acc.get("network") == "eip155:8453")
            return ok, ("402 quote ok: $0.01 USDC on Base" if ok
                        else "402 quote mismatch: %s" % acc)
        except Exception as ex:
            return False, "402 body unreadable: %r" % ex
    except Exception as ex:
        return False, "probe failed: %r" % ex


def evaluate(snap):
    """CONDITION: frozen policy over the snapshot. Pure function."""
    pools = [p for p in snap.get("pools", []) if isinstance(p.get("apy"), (int, float))]
    if not pools:
        return {"fire": False, "reason": "no-pools-in-snapshot"}
    top = max(pools, key=lambda p: p["apy"])
    age = snapshot_age_s(snap)
    if age > MAX_AGE_S:
        return {"fire": False, "reason": "snapshot-stale", "age_s": round(age),
                "top": top["symbol"], "top_apy": top["apy"]}
    if top["apy"] < THRESHOLD:
        return {"fire": False, "reason": "below-threshold",
                "top": top["symbol"], "top_apy": top["apy"],
                "threshold": THRESHOLD}
    return {"fire": True, "reason": "threshold-met", "top": top,
            "threshold": THRESHOLD, "age_s": round(age)}


def build_plan(decision, snap):
    """ACTION: frozen execution plan — exact steps, no inference later."""
    if not decision["fire"]:
        steps = [{"seq": 1, "action": "notify",
                  "params": {"channel": "keeperhub-audit",
                             "message": "keeper-x402 idle: %s" % decision["reason"]}}]
    else:
        t = decision["top"]
        steps = [
            {"seq": 1, "action": "keeperhub.web3/check-balance",
             "params": {"network": "8453"}},
            {"seq": 2, "action": "keeperhub.condition.apy-gate",
             "params": {"symbol": t["symbol"], "apy_pct": t["apy"],
                        "threshold": THRESHOLD, "operator": ">="}},
            {"seq": 3, "action": "keeperhub.notify.route",
             "params": {"channel": "audit",
                        "message": "route $100 -> %s %s on %s @ %s%%" % (
                            t["project"], t["symbol"], t["chain"], t["apy"])}}]
    body = json.dumps({"fetched_at": snap.get("fetched_at"), "decision": decision,
                       "steps": steps}, sort_keys=True)
    return {"steps": steps,
            "plan_hash": hashlib.sha256(body.encode()).hexdigest()[:16]}


def audit(record):
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def run(mode):
    t0 = now()
    snap, source = load_snapshot(mode)
    paywall_ok, paywall_detail = probe_paywall() if mode == "live" else (None, "skipped (demo mode)")
    decision = evaluate(snap)
    plan = build_plan(decision, snap)
    result = {"run_at": t0, "mode": mode, "api_base": API_BASE,
              "snapshot_source": source,
              "snapshot_fetched_at": snap.get("fetched_at"),
              "pool_count": snap.get("count", len(snap.get("pools", []))),
              "paywall_live": paywall_ok, "paywall_detail": paywall_detail,
              "policy": {"min_apy_pct": THRESHOLD, "max_age_s": MAX_AGE_S},
              "decision": decision, "execution_plan": plan,
              "keeperhub_binding": "keeperhub_workflow.json (import or MCP create_workflow)"}
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    audit({"ts": t0, "mode": mode, "trigger": source,
           "simulation": {"wouldRevert": False, "decision": decision["reason"]},
           "plan_hash": plan["plan_hash"], "outcome": "planned",
           "gas_used": "n/a (dry-run, nothing broadcast)"})
    print(json.dumps(result, indent=2))
    print("wrote %s and appended %s" % (OUT_JSON, AUDIT_LOG))
    return result


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("demo", "live") else "demo"
    run(mode)
