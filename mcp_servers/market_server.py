"""
Market Data MCP Server
======================
Exposes CoinGecko market data as MCP tools so the agents fetch live prices and
OHLC history by *calling tools over MCP* rather than hard-coding HTTP calls.

Tools:
  * get_price(coin_id)            -> current price, market cap, 24h change
  * get_ohlc_history(coin_id, days) -> OHLC candles for indicator math

Respects MOCK_MODE so the tools still fire (returning baked-in data) with zero
internet — the live demo works online or offline.

Run standalone:  python mcp_servers/market_server.py
"""

import json
import os
import sys

# Make the project root importable when launched as a subprocess.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from mcp.server.fastmcp import FastMCP

from config import COINGECKO_BASE, REQUEST_TIMEOUT, use_mock
from lib.mock_data import mock_market_data

mcp = FastMCP("market-data-server")
_HEADERS = {"User-Agent": "ai-crypto-trading-desk/1.0"}


@mcp.tool()
def get_price(coin_id: str = "bitcoin") -> str:
    """Get the current price, market cap and 24h % change for a crypto coin.
    Returns JSON with name, symbol, current_price, market_cap, price_change_24h."""
    if use_mock():
        m = mock_market_data(coin_id)
        return json.dumps({k: m[k] for k in
                           ("name", "symbol", "current_price", "market_cap", "price_change_24h")})

    resp = requests.get(
        f"{COINGECKO_BASE}/coins/markets",
        params={"vs_currency": "usd", "ids": coin_id, "per_page": 1, "page": 1, "sparkline": "false"},
        headers=_HEADERS, timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"No market data for '{coin_id}'")
    c = data[0]
    return json.dumps({
        "name": c["name"],
        "symbol": c["symbol"].upper(),
        "current_price": c["current_price"],
        "market_cap": c["market_cap"],
        "price_change_24h": c.get("price_change_percentage_24h") or 0.0,
    })


@mcp.tool()
def get_ohlc_history(coin_id: str = "bitcoin", days: int = 30) -> str:
    """Get OHLC price candles for a coin over `days` days.
    Returns JSON list of [timestamp_ms, open, high, low, close] rows."""
    if use_mock():
        m = mock_market_data(coin_id)
        df = m["history"]
        rows = df[["timestamp", "open", "high", "low", "close"]].values.tolist()
        return json.dumps(rows)

    resp = requests.get(
        f"{COINGECKO_BASE}/coins/{coin_id}/ohlc",
        params={"vs_currency": "usd", "days": days},
        headers=_HEADERS, timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return json.dumps(resp.json())


if __name__ == "__main__":
    if "--test" in sys.argv:
        # Tools are plain functions — call them directly to verify.
        print(get_price("bitcoin")[:200])
        print(get_ohlc_history("bitcoin")[:120], "...")
    else:
        mcp.run()
