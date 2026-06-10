"""
Stocks MCP Server
=================
Exposes equity data (Yahoo Finance, free, no key) as MCP tools, so the same
agent pipeline can analyse a second market — "any market". Mirrors the
market-data-server shape so downstream agents are market-agnostic.

Tools:
  * get_quote(symbol)               -> price, prev-close-based 24h change, name
  * get_ohlc_history(symbol, range) -> OHLC candles for indicators

Respects MOCK_MODE (baked-in data offline).

Run standalone:  python mcp_servers/stocks_server.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from mcp.server.fastmcp import FastMCP

from config import YAHOO_CHART, REQUEST_TIMEOUT, SUPPORTED_STOCKS, use_mock
from lib.mock_data import mock_market_data

mcp = FastMCP("stocks-server")
_HEADERS = {"User-Agent": "Mozilla/5.0 (ai-crypto-trading-desk)"}


def _chart(symbol: str, rng: str):
    resp = requests.get(YAHOO_CHART.format(symbol=symbol),
                        params={"range": rng, "interval": "1d"},
                        headers=_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    result = resp.json()["chart"]["result"]
    if not result:
        raise ValueError(f"No data for '{symbol}'")
    return result[0]


@mcp.tool()
def get_quote(symbol: str = "AAPL") -> str:
    """Get the current price, 24h % change and market cap for a stock ticker.
    Returns JSON with name, symbol, current_price, market_cap, price_change_24h."""
    if use_mock():
        m = mock_market_data(symbol)
        return json.dumps({k: m[k] for k in
                           ("name", "symbol", "current_price", "market_cap", "price_change_24h")})

    r = _chart(symbol, "5d")
    meta = r["meta"]
    closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    # True 1-day move = latest close vs the prior day's close.
    prev = closes[-2] if len(closes) >= 2 else meta.get("chartPreviousClose") or price
    change = (price / prev - 1) * 100 if prev else 0.0
    return json.dumps({
        "name": SUPPORTED_STOCKS.get(symbol, symbol),
        "symbol": symbol,
        "current_price": price,
        "market_cap": meta.get("marketCap"),  # often absent in chart meta -> None
        "price_change_24h": change,
    })


@mcp.tool()
def get_ohlc_history(symbol: str = "AAPL", range: str = "3mo") -> str:
    """Get daily OHLC candles for a stock over `range` (e.g. 1mo, 3mo, 6mo).
    Returns JSON list of [timestamp_ms, open, high, low, close] rows."""
    if use_mock():
        m = mock_market_data(symbol)
        return json.dumps(m["history"][["timestamp", "open", "high", "low", "close"]].values.tolist())

    r = _chart(symbol, range)
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append([t * 1000, o, h, l, c])
    if not rows:
        raise ValueError(f"No OHLC history for '{symbol}'")
    return json.dumps(rows)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print(get_quote("AAPL"))
        print(get_ohlc_history("AAPL")[:120], "...")
    else:
        mcp.run()
