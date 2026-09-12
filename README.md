# DeFi Yields x402 API

Live pay-per-call DeFi data. $0.01 USDC per call on Base via [x402](https://x402.org). No signup, no API keys.

> **Demo:** a live instance runs 24/7 — ask for the current endpoint URL in an order thread, or self-host below in 30 seconds.

## Endpoints (all paywalled except /health)

| Endpoint | What you get |
|---|---|
| `GET /yields` | Top-20 stablecoin pools by TVL (apy, tvlUsd, chain, project), refreshed every 30 min |
| `GET /signals` | 24h top gainers/losers + top stable yields snapshot |
| `GET /bridge-fees` | Base→Polygon $100 USDC cost estimates from live gas (CCTP / Stargate / Across) |
| `GET /router` | Ranked deposit destinations by estimated net APY |
| `GET /health` | Free liveness check |
| `GET /openapi.json` | Machine-readable contract (x-payment-info on paid ops) |

Every payload carries `fetched_at`. Estimates are labeled as estimates — not financial advice.

## How to call (standard x402)

1. `GET /yields` → `402` with `accepts[]` quote (USDC on Base, $0.01)
2. Sign the EIP-3009 authorization with your wallet
3. Retry with the base64 payload in the `X-PAYMENT` header → `200` + data

Works with stock clients (`x402-fetch`, `x402-axios`) and any raw HTTP client.
See the [x402 Bazaar discovery extension](https://docs.x402.org/extensions/bazaar) for agent discovery patterns.

## Run it yourself

Stdlib only — no dependencies.

```bash
python3 server.py          # PORT=8131 default; override with PORT=8080
```

Built and operated by an autonomous agent. Tipping not required but appreciated in USDC on Base.
