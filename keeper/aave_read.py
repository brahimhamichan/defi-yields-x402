#!/usr/bin/env python3
"""aave_read: third-party protocol leg for keeper-x402 v2.

Live READ integration with Aave V3 on Base (no keys, no spend, stdlib only):
  Pool.getReserveData(USDC) via free public Base RPC -> supply liquidity rate,
  variable borrow rate, last-update timestamp, block number.

  Aave V3 Pool (Base):            0xA238Dd80C259a72e81d7e4664a9801593F98d1c5
  USDC (Base):                    0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
  getReserveData(address):        selector 0x35ea6a75

Rates are in ray (1e27). supply_apy_pct = liquidityRate / 1e27 * 100.
utilization is estimated as liquidityRate / variableBorrowRate (labeled as an
estimate: exact utilization needs totalSupply/totalBorrows; the ratio equals
utilization * (1 - reserveFactor), so it is a slight underestimate).

No mocks on this path: every field comes from a live eth_call. RPCs are tried
in order; the responding endpoint is recorded in the artifact.
"""
import json
import time
import urllib.request

RPCS = [
    "https://base.publicnode.com",
    "https://1rpc.io/base",
    "https://mainnet.base.org",
]
CHAIN_ID = 8453
POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
GET_RESERVE_DATA = "0x35ea6a75" + "0" * 24 + USDC[2:].lower()
RAY = 10 ** 27


def rpc(url, method, params, timeout=20):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "keeper-x402-v2/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if out.get("error"):
        raise RuntimeError("rpc error: %s" % out["error"])
    return out["result"]


def decode_reserve_data(hexdata):
    """Decode the 15-word getReserveData return. Pure function (unit-tested)."""
    h = hexdata[2:] if hexdata.startswith("0x") else hexdata
    if len(h) < 15 * 64:
        raise ValueError("short getReserveData payload: %d hex chars" % len(h))
    w = [int(h[i:i + 64], 16) for i in range(0, 15 * 64, 64)]
    liq_ray, var_ray = w[2], w[4]
    return {
        "liquidity_rate_ray": str(liq_ray),
        "variable_borrow_rate_ray": str(var_ray),
        "supply_apy_pct": round(liq_ray / RAY * 100, 4),
        "variable_borrow_apy_pct": round(var_ray / RAY * 100, 4),
        "utilization_est": round(liq_ray / var_ray, 4) if var_ray else None,
        "last_update_ts": w[6],
        "a_token": "0x%040x" % w[8],
    }


def read_aave_usdc():
    """Live read. Returns (record, rpc_url_used). Raises on total failure."""
    last_err = None
    for url in RPCS:
        try:
            chain = int(rpc(url, "eth_chainId", []), 16)
            if chain != CHAIN_ID:
                raise RuntimeError("wrong chain %r" % chain)
            block_hex = rpc(url, "eth_blockNumber", [])
            block = int(block_hex, 16)
            raw = rpc(url, "eth_call",
                      [{"to": POOL, "data": GET_RESERVE_DATA}, block_hex])
            rec = decode_reserve_data(raw)
            blk = rpc(url, "eth_getBlockByNumber", [block_hex, False])
            rec.update({
                "protocol": "aave-v3", "chain": "Base", "chain_id": chain,
                "asset": "USDC", "asset_address": USDC, "pool": POOL,
                "block_number": block,
                "block_timestamp": int(blk["timestamp"], 16),
                "rpc_url": url,
                "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            return rec, url
        except Exception as e:  # noqa: BLE001 - try next RPC
            last_err = "%s: %r" % (url, e)
    raise RuntimeError("all Base RPCs failed; last: %s" % last_err)


def selftest():
    """Deterministic unit check of the decoder (no network)."""
    liq, var, ts = 4_500_000_000_000_000_000_000_000, 60_000_000_000_000_000_000_000_000, 1786500000
    words = [0] * 15
    words[2], words[4], words[6] = liq, var, ts
    words[8] = int("4e65fe4dba92790696d040ac24aa414708f5c0ab", 16)
    payload = "0x" + "".join("%064x" % v for v in words)
    d = decode_reserve_data(payload)
    assert d["supply_apy_pct"] == round(liq / RAY * 100, 4) == 0.45, d
    assert d["variable_borrow_apy_pct"] == 6.0, d
    assert d["utilization_est"] == round(liq / var, 4) == 0.075, d
    assert d["last_update_ts"] == ts, d
    assert d["a_token"] == "0x4e65fe4dba92790696d040ac24aa414708f5c0ab", d
    try:
        decode_reserve_data("0x1234")
        raise SystemExit("selftest FAILED: short payload accepted")
    except ValueError:
        pass
    print("aave_read selftest ok: decoder math verified (0.45%% supply, 6.0%% borrow, 0.075 util)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        rec, url = read_aave_usdc()
        print(json.dumps(rec, indent=2))
