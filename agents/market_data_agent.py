"""
Market Data Agent
=================
Fetches current price + OHLC history for EITHER market:
  * crypto -> market-data-server (CoinGecko)  get_price / get_ohlc_history
  * stocks -> stocks-server (Yahoo Finance)   get_quote / get_ohlc_history

Data is fetched by calling MCP tools; on failure it degrades direct -> cache ->
mock so the live demo never crashes.

It also convenes a 4-member **Data Validation Council** that debates whether the
fetched data is trustworthy (source, liquidity, freshness, anomaly) and votes a
data-trust verdict that flows downstream.
"""

import json
import time

import pandas as pd
import requests

from config import (COINGECKO_BASE, REQUEST_TIMEOUT, CACHE_TTL_SECONDS, HISTORY_DAYS,
                    market_of, use_mock, use_mcp)
from lib import mcp_client
from lib.debate import member, make_panel
from lib.mock_data import mock_market_data

_CACHE: dict[str, tuple[float, dict]] = {}
_HEADERS = {"User-Agent": "ai-crypto-trading-desk/1.0"}


def _get(url: str, params: dict | None = None):
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _history_df(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


# ---------------------------------------------------------------------------
# MCP fetch (per market)
# ---------------------------------------------------------------------------
def _fetch_via_mcp(asset_id: str, market: str):
    before = len(mcp_client.get_mcp_log())
    if market == "stocks":
        results = mcp_client.call_tools("stocks", [
            ("get_quote", {"symbol": asset_id}),
            ("get_ohlc_history", {"symbol": asset_id, "range": "3mo"}),
        ])
        price_raw, ohlc_raw = results.get("get_quote"), results.get("get_ohlc_history")
    else:
        results = mcp_client.call_tools("market", [
            ("get_price", {"coin_id": asset_id}),
            ("get_ohlc_history", {"coin_id": asset_id, "days": HISTORY_DAYS}),
        ])
        price_raw, ohlc_raw = results.get("get_price"), results.get("get_ohlc_history")
    calls = mcp_client.get_mcp_log()[before:]

    if not price_raw or not ohlc_raw:
        return None
    try:
        price = json.loads(price_raw)
        history = _history_df(json.loads(ohlc_raw))
    except (ValueError, TypeError):
        return None
    if history.empty:
        return None

    return {
        "asset_id": asset_id, "market": market,
        "name": price["name"], "symbol": price["symbol"],
        "current_price": price["current_price"], "market_cap": price.get("market_cap"),
        "price_change_24h": price.get("price_change_24h") or 0.0,
        "history": history,
        "source": "mock" if use_mock() else "mcp",
        "notice": "Mock mode — MCP tools served baked-in offline data." if use_mock() else None,
        "mcp_calls": calls,
    }


def _fetch_direct(asset_id: str, market: str) -> dict:
    """Direct HTTP fallback (crypto only — stocks always go through MCP/mock)."""
    if market == "stocks":
        raise RuntimeError("no direct stocks path")
    markets = _get(f"{COINGECKO_BASE}/coins/markets",
                   {"vs_currency": "usd", "ids": asset_id, "per_page": 1, "page": 1, "sparkline": "false"})
    if not markets:
        raise ValueError(f"No market data returned for '{asset_id}'")
    coin = markets[0]
    ohlc = _get(f"{COINGECKO_BASE}/coins/{asset_id}/ohlc", {"vs_currency": "usd", "days": HISTORY_DAYS})
    history = _history_df(ohlc)
    if history.empty:
        raise ValueError(f"No price history for '{asset_id}'")
    return {
        "asset_id": asset_id, "market": market,
        "name": coin["name"], "symbol": coin["symbol"].upper(),
        "current_price": coin["current_price"], "market_cap": coin["market_cap"],
        "price_change_24h": coin.get("price_change_percentage_24h") or 0.0,
        "history": history, "source": "direct",
        "notice": "MCP unavailable — fetched directly from CoinGecko.", "mcp_calls": [],
    }


# ---------------------------------------------------------------------------
# Data Validation Council — 4 sub-agents debate data trust
# ---------------------------------------------------------------------------
def _build_panel(p: dict) -> dict:
    source = p["source"]
    members = []

    # 1. Source reliability
    if source in ("mcp", "live", "direct"):
        members.append(member("Source Reliability", "GOOD", 88,
                              f"Fetched fresh via {source.upper()} — primary source is responding."))
    elif source == "cached":
        members.append(member("Source Reliability", "DEGRADED", 55,
                              "Serving cached data — live source was unavailable."))
    else:
        members.append(member("Source Reliability", "DEGRADED", 50,
                              "Running on offline mock data — treat figures as illustrative."))

    # 2. Liquidity (market cap)
    mcap = p.get("market_cap")
    if mcap and mcap > 5e10:
        members.append(member("Liquidity Check", "GOOD", 85, f"Large cap (${mcap/1e9:,.0f}B) — deep, liquid market."))
    elif mcap and mcap > 5e9:
        members.append(member("Liquidity Check", "GOOD", 70, f"Mid cap (${mcap/1e9:,.0f}B) — adequate liquidity."))
    else:
        members.append(member("Liquidity Check", "DEGRADED", 60, "Market cap unavailable — sizing with caution."))

    # 3. Freshness (last candle age)
    last_ms = int(p["history"]["timestamp"].iloc[-1])
    age_h = (time.time() * 1000 - last_ms) / 3.6e6
    if age_h <= 36:
        members.append(member("Freshness", "GOOD", 84, f"Latest candle is {age_h:.0f}h old — current."))
    elif age_h <= 96:
        members.append(member("Freshness", "DEGRADED", 60, f"Latest candle is {age_h:.0f}h old — slightly stale."))
    else:
        members.append(member("Freshness", "STALE", 45, f"Latest candle is {age_h/24:.0f}d old — stale."))

    # 4. Anomaly (24h move sanity)
    chg = abs(p.get("price_change_24h") or 0.0)
    if chg < 15:
        members.append(member("Anomaly Scan", "GOOD", 82, f"24h move {chg:.1f}% is within normal range."))
    elif chg < 30:
        members.append(member("Anomaly Scan", "DEGRADED", 58, f"24h move {chg:.1f}% is large — verify before acting."))
    else:
        members.append(member("Anomaly Scan", "STALE", 40, f"24h move {chg:.1f}% looks anomalous — possible bad tick."))

    return make_panel("Data Validation Council", members, neutral="DEGRADED")


def get_market_data(asset_id: str = "bitcoin", market: str | None = None) -> dict:
    """Always-succeeds market-data fetch (never raises)."""
    market = market or market_of(asset_id)
    now = time.time()
    cached = _CACHE.get(asset_id)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    payload = None
    if use_mcp():
        payload = _fetch_via_mcp(asset_id, market)

    if payload is None:
        try:
            if use_mock():
                payload = mock_market_data(asset_id)
                payload.update({"market": market, "mcp_calls": []})
            else:
                payload = _fetch_direct(asset_id, market)
        except Exception as exc:
            if cached:
                stale = dict(cached[1])
                stale["source"] = "cached"
                stale["notice"] = f"Live data unavailable — showing cached data ({int(now - cached[0])}s old)."
                return stale
            payload = mock_market_data(asset_id)
            payload.update({"market": market, "mcp_calls": [],
                            "notice": f"Live data unavailable ({type(exc).__name__}) — using offline demo data."})

    payload["panel"] = _build_panel(payload)
    _CACHE[asset_id] = (now, payload)
    return payload
