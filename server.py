#!/usr/bin/env python3
"""x402 pay-per-call DeFi yields API. Stdlib only — no dependencies.

Flow:  GET /yields (no payment) -> 402 + quote JSON (accepts USDC/base)
        client pays, retries with X-PAYMENT header -> verify -> 200 data.
GET /health is free. GET /.well-known/x402 describes the service.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAY_TO = "0xce81d12cce65bba50b017857a98526b021004b97"  # ours, public
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
NETWORK = "eip155:8453"  # CAIP-2 (v2 validators reject bare "base")
PUBLIC_BASE = "https://devbox.tail08c9f0.ts.net"  # stable public base
SCHEME = "exact"
PRICE_ATOMIC = "10000"  # $0.01 USDC (6 decimals)
X402_VERSION = 2  # v2: agentcash/x402scan require v2 (v1 unsupported by them)
FACILITATOR_VERIFY = "https://x402.org/facilitator/verify"  # public, no key
FACILITATOR_SETTLE = "https://x402.org/facilitator/settle"  # public, no key
LLAMA_POOLS = "https://yields.llama.fi/pools"
CACHE_TTL = 1800  # 30 min
PORT = int(os.environ.get("PORT", "8131"))
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(HERE, "yields_cache.json")
FALLBACK = {"fallback": True, "endpoint": "/yields", "fetched_at": None,
            "count": 0, "pools": [],
            "note": "live snapshot unavailable (fetch failed, no cache yet)"}


def fetch_llama_top20():
    """Fetch pools, keep top-20 stablecoin by TVL. Raises on failure."""
    req = urllib.request.Request(LLAMA_POOLS, headers={"User-Agent": "x402-api/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    pools = data.get("data", [])
    stables = [p for p in pools if p.get("stablecoin") is True
               and isinstance(p.get("tvlUsd"), (int, float))]
    stables.sort(key=lambda p: p["tvlUsd"], reverse=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = [{"pool": p.get("pool"), "chain": p.get("chain"),
             "project": p.get("project"), "symbol": p.get("symbol"),
             "tvlUsd": p.get("tvlUsd"), "apy": p.get("apy"),
             "apyBase": p.get("apyBase"), "apyReward": p.get("apyReward")}
            for p in stables[:20]]
    return {"endpoint": "/yields", "fetched_at": now, "count": len(rows),
            "pools": rows}


def load_cache():
    try:
        with open(CACHE_FILE) as f:
            c = json.load(f)
        if isinstance(c, dict) and c.get("pools"):
            return c
    except Exception:
        pass
    return None


def save_cache(payload):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(payload, f)
    except Exception:
        pass


def ensure_data():
    """Serve cache; refresh if stale. Never raises — falls back, never 500."""
    c = load_cache()
    if c and time.time() - c.get("_ts", 0) < CACHE_TTL:
        return c
    try:
        fresh = fetch_llama_top20()
        fresh["_ts"] = time.time()
        save_cache(fresh)
        return fresh
    except Exception:
        if c:
            return c
        return dict(FALLBACK)


def openapi_spec():
    paid = {}
    descs = {"/yields": "Top-20 stablecoin pools by TVL (apy, tvlUsd, chain, project).",
             "/signals": "24h movers + top stable yields snapshot.",
             "/bridge-fees": "Base->Polygon $100 USDC cost estimates from live gas.",
             "/router": "Ranked deposit destinations by est. net APY."}
    for path, desc in descs.items():
        paid[path] = {
            "get": {
                "summary": desc,
                "requestBody": {"required": False,
                               "content": {"application/json": {
                                   "schema": {"type": "object",
                                              "properties": {}}}},
                               },
                "responses": {"200": {"description": "Data snapshot"},
                              "402": {"description": "Payment Required"}},
                "x-payment-info": {
                    "price": {"fixed": {"mode": "fixed", "currency": "USD",
                                        "amount": "0.01"}},
                    "protocols": [{"x402": {}}]}}}
    return {"openapi": "3.1.0",
            "info": {"title": "DeFi Data Snapshots (x402)",
                     "version": "1.1.0",
                     "description": "Pay-per-call DeFi data: yields, signals, bridge fees, deposit router. $0.01 USDC/call on Base via x402. No signup: call -> 402 quote -> pay -> retry with X-PAYMENT.",
                     "x-guidance": "GET /yields (or /signals, /bridge-fees, /router). Expect 402 with accepts[] (USDC on Base, $0.01). Sign EIP-3009 transfer to payTo, retry with base64 payload in X-PAYMENT header. Data is JSON with fetched_at timestamps."},
            "servers": [{"url": "https://devbox.tail08c9f0.ts.net"}],
            "paths": {**paid, "/health": {
                "get": {"summary": "Free health check",
                        "responses": {"200": {"description": "ok"}}}}}}


def requirement(resource="/yields"):
    return {"scheme": SCHEME, "network": NETWORK, "asset": USDC_BASE,
            "payTo": PAY_TO, "amount": PRICE_ATOMIC,
            "maxAmountRequired": PRICE_ATOMIC,  # v1 compat alongside v2 amount
            "resource": {"url": PUBLIC_BASE + resource,
                         "description": "DeFi data snapshot",
                         "mimeType": "application/json"},
            "maxTimeoutSeconds": 300}


EXAMPLES = {
    "/yields": {"endpoint": "/yields", "fetched_at": "2026-09-08T00:00:00Z",
                "count": 20,
                "pools": [{"pool": "0dbb5021-00c7-40e2-9e2b-a757f4305ebf",
                           "chain": "Solana", "project": "jupiter-lend",
                           "symbol": "JUPUSD", "tvlUsd": 57536005,
                           "apy": 6.21, "apyBase": 5.21, "apyReward": 0.99}]},
    "/signals": {"endpoint": "/signals", "fetched_at": "2026-09-08T00:00:00Z",
                 "top_gainers_24h": [{"symbol": "btc", "price": 79675.0,
                                      "chg24h_pct": 1.2}]},
    "/bridge-fees": {"endpoint": "/bridge-fees", "fetched_at": "2026-09-08T00:00:00Z",
                     "route": "Base USDC -> Polygon USDC, $100",
                     "estimates_usd": {"cctp": {"total": 0.01}}},
    "/router": {"endpoint": "/router", "fetched_at": "2026-09-08T00:00:00Z",
                "deposit_usd": 100.0,
                "ranking": [{"symbol": "JUPUSD", "est_net_apy_pct": 6.2}]},
}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_signals():
    """24h movers (CoinGecko) + top stable yields (cache). Honest snapshot."""
    try:
        rq = urllib.request.Request(
            "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
            "&order=market_cap_desc&per_page=25&page=1"
            "&price_change_percentage=24h", headers=UA)
        with urllib.request.urlopen(rq, timeout=20) as r:
            coins = json.load(r)
        rows = [{"symbol": c.get("symbol"), "price": c.get("current_price"),
                 "chg24h_pct": round(c.get("price_change_percentage_24h") or 0, 2)}
                for c in coins]
        gain = sorted([m for m in rows if m["chg24h_pct"] is not None],
                      key=lambda m: -m["chg24h_pct"])[:5]
        lose = sorted([m for m in rows if m["chg24h_pct"] is not None],
                      key=lambda m: m["chg24h_pct"])[:5]
    except Exception:
        gain, lose = [], []
    c = load_cache() or {}
    top_y = sorted((c.get("pools") or []), key=lambda p: -(p.get("apy") or 0))[:5]
    return {"endpoint": "/signals", "fetched_at": _now(),
            "note": "experimental momentum/yield snapshot, not financial advice",
            "top_gainers_24h": gain, "top_losers_24h": lose,
            "top_stable_yields": [{"symbol": p.get("symbol"),
                                   "project": p.get("project"),
                                   "chain": p.get("chain"),
                                   "apy": p.get("apy")} for p in top_y]}


def _gas_price_wei(url):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_gasPrice",
                       "params": []}).encode()
    rq = urllib.request.Request(url, data=body,
                                headers={"Content-Type": "application/json",
                                         "User-Agent": "x402-api/1.0"})
    with urllib.request.urlopen(rq, timeout=12) as r:
        return int(json.load(r)["result"], 16)


def build_router(amount_usd=100.0):
    """Where to deposit $X: net APY = yield - bridge - gas, ranked. Estimates."""
    c = load_cache() or {}
    pools = sorted((c.get("pools") or []), key=lambda p: -(p.get("apy") or 0))[:10]
    try:
        br = build_bridge()
        cctp_cost = br["estimates_usd"]["cctp"]["total"]
    except Exception:
        cctp_cost = 0.05
    rows = []
    for p in pools:
        apy = p.get("apy") or 0
        gross = amount_usd * apy / 100.0
        move = 0.0 if (p.get("chain") or "").lower() == "base" else cctp_cost
        net_pct = (gross - move) / amount_usd * 100.0
        rows.append({"symbol": p.get("symbol"), "project": p.get("project"),
                     "chain": p.get("chain"), "apy_pct": apy,
                     "est_move_cost_usd": round(move, 4),
                     "est_net_apy_pct": round(net_pct, 3)})
    rows.sort(key=lambda r: -r["est_net_apy_pct"])
    return {"endpoint": "/router", "fetched_at": _now(),
            "deposit_usd": amount_usd, "ranking": rows,
            "note": "estimates from live yields+gas at fetched_at, not financial advice"}


def build_bridge():
    """Base->Polygon $100 USDC estimates from LIVE gas + fee schedules. Labeled."""
    base_gas = _gas_price_wei("https://base.publicnode.com")
    poly_gas = _gas_price_wei("https://polygon.publicnode.com")
    rq = urllib.request.Request(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=ethereum,matic-network&vs_currencies=usd", headers=UA)
    with urllib.request.urlopen(rq, timeout=15) as r:
        px = json.load(r)
    eth, pol = px["ethereum"]["usd"], px["matic-network"]["usd"]
    base_leg = 250000 * base_gas * 1e-18 * eth      # ~250k gas on Base
    poly_leg = 180000 * poly_gas * 1e-18 * pol      # ~180k gas on Polygon
    cctp = round(base_leg + poly_leg, 4)
    stargate = round(0.06 + base_leg + 0.005, 4)    # 6bps on $100 + gas
    return {"endpoint": "/bridge-fees", "fetched_at": _now(),
            "route": "Base USDC -> Polygon USDC, $100",
            "inputs": {"base_gas_gwei": round(base_gas / 1e9, 4),
                       "polygon_gas_gwei": round(poly_gas / 1e9, 2),
                       "eth_usd": eth, "pol_usd": pol},
            "estimates_usd": {
                "cctp": {"total": cctp, "note": "no protocol fee; ~15-20min"},
                "stargate_v2": {"total": stargate, "note": "0.06% fee; ~1-3min"},
                "across": {"total": round(base_leg + 0.03, 4),
                           "note": "dynamic relayer fee; seconds"}},
            "note": "estimates from live gas at fetched_at; re-quote before sending"}


def quote_402(resource="/yields", reason="payment required"):
    return {"x402Version": X402_VERSION, "error": reason,
            "resource": {"url": PUBLIC_BASE + resource,
                         "description": "DeFi data snapshot",
                         "mimeType": "application/json"},
            "accepts": [requirement(resource)],
            "extensions": {"bazaar": {"schema": {"properties": {
                "input": {"properties": {
                    "body": {"type": "object", "properties": {}}}},
                "output": {"properties": {
                    "example": EXAMPLES.get(
                        resource, {"endpoint": resource})}}}}}}}


# ---- VERIFY WIRING POINT (boss: rewire here if facilitator shape changes) ----
# Live shape (probed 2026-09-08): POST /verify
#   {x402Version, paymentPayload (decoded X-PAYMENT JSON), paymentRequirements}
# Cloudflare 403s the default Python-urllib UA, so we send our own UA.
UA = {"Content-Type": "application/json", "User-Agent": "x402-api/1.0"}


def verify_payment(payment_header, req):
    """POST payment to public facilitator /verify. Returns (ok, reason).

    Any failure => invalid (402 again). Never raises, never serves on doubt.
    """
    raw = (payment_header or "").strip()
    if not raw:
        return False, "empty-payment-header"
    try:  # X-PAYMENT must be base64-JSON or raw JSON; decode for the facilitator
        try:
            payload = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
        except Exception:
            payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload not an object")
    except Exception:
        return False, "malformed-payment-header"
    body = json.dumps({"x402Version": X402_VERSION, "paymentPayload": payload,
                       "paymentRequirements": req}).encode()
    try:
        rq = urllib.request.Request(FACILITATOR_VERIFY, data=body, headers=UA,
                                    method="POST")
        with urllib.request.urlopen(rq, timeout=8) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:  # facilitator rejects w/ 4xx + JSON
        try:
            resp = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return False, "facilitator-http-%s" % e.code
    except Exception as e:
        return False, "facilitator-error: %r" % e
    if isinstance(resp, dict) and resp.get("isValid") is True:
        return True, "facilitator-valid"
    reason = (resp.get("invalidReason") or resp) if isinstance(resp, dict) else resp
    return False, "facilitator-invalid: %s" % reason


def settle_payment(payment_header, req):
    """POST payment to public facilitator /settle to capture funds.

    Called AFTER verify-ok, BEFORE serving. Returns (ok, info).
    Never raises. If unsettled, we must NOT serve (no free data).
    """
    raw = (payment_header or "").strip()
    try:
        try:
            payload = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
        except Exception:
            payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload not an object")
    except Exception:
        return False, "malformed-payment-header"
    body = json.dumps({"x402Version": X402_VERSION, "paymentPayload": payload,
                       "paymentRequirements": req}).encode()
    try:
        rq = urllib.request.Request(FACILITATOR_SETTLE, data=body, headers=UA,
                                    method="POST")
        with urllib.request.urlopen(rq, timeout=15) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            resp = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return False, "settle-http-%s" % e.code
    except Exception as e:
        return False, "settle-error: %r" % e
    if isinstance(resp, dict) and resp.get("success") is True:
        return True, "settled: %s" % resp.get("transaction")
    reason = ((resp.get("errorReason") or resp.get("error")) or resp) if isinstance(resp, dict) else resp
    return False, "settle-failed: %s" % reason


class H(BaseHTTPRequestHandler):
    server_version = "x402-yields/1.0"

    def _json(self, code, obj, extra=()):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-PAYMENT, PAYMENT-SIGNATURE, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-PAYMENT, PAYMENT-SIGNATURE, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _paywall(self, path, reason):
        q = quote_402(path, reason)
        b64 = base64.b64encode(json.dumps(q).encode()).decode()
        self._json(402, q, [("PAYMENT-REQUIRED", b64)])

    def do_GET(self):
        try:
            with open(os.path.join(HERE, "..", ".state", "probe.log"), "a") as f:
                f.write("%s %s %s %s\n" % (
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    self.command, self.path,
                    (self.headers.get("User-Agent") or "")[:80]))
        except Exception:
            pass
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/health":
            self._json(200, {"status": "ok", "service": "x402-yields",
                             "time": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime())})
        elif path == "/.well-known/x402":
            self._json(200, {"x402Version": X402_VERSION,
                             "service": "DeFi stablecoin yields snapshot",
                             "chains": [NETWORK], "asset": USDC_BASE,
                             "payTo": PAY_TO, "priceAtomic": PRICE_ATOMIC,
                             "price": "$0.01 USDC/call",
                             "endpoints": {
                                 "/yields": {"price": PRICE_ATOMIC, "auth": "X-PAYMENT"},
                                 "/signals": {"price": PRICE_ATOMIC, "auth": "X-PAYMENT"},
                                 "/bridge-fees": {"price": PRICE_ATOMIC, "auth": "X-PAYMENT"},
                                 "/router": {"price": PRICE_ATOMIC, "auth": "X-PAYMENT"},
                                 "/health": {"price": "free"},
                                 "/.well-known/x402": {"price": "free"}}})
        elif path == "/openapi.json":
            self._json(200, openapi_spec())
        elif path in ("/yields", "/signals", "/bridge-fees", "/router"):
            pay = self.headers.get("X-PAYMENT") or self.headers.get("PAYMENT-SIGNATURE")
            if not pay:
                self._paywall(path, "payment required: retry with X-PAYMENT header")
                return
            ok, reason = verify_payment(pay, requirement(path))
            if not ok:
                self._paywall(path, reason)
                return
            ok, info = settle_payment(pay, requirement(path))
            if not ok:
                self._paywall(path, info)
                return
            try:
                if path == "/signals":
                    data = build_signals()
                elif path == "/bridge-fees":
                    data = build_bridge()
                elif path == "/router":
                    data = build_router()
                else:
                    data = ensure_data()
            except Exception as e:
                self._json(500, {"error": "snapshot failed: %r" % e})
                return
            data["_settlement"] = info
            self._json(200, data, [("X-PAYMENT-RESPONSE",
                                    base64.b64encode(b'{"success":true}').decode())])
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    try:  # warm cache at startup; failures fall back to disk/static
        if not load_cache():
            ensure_data()
    except Exception:
        pass
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
