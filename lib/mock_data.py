"""
Baked-in realistic data for MOCK_MODE and for graceful fallback when the
CoinGecko API is unreachable or rate-limited. Generates a deterministic OHLC
random-walk per coin so indicators, charts, and risk numbers all look real.
"""

import random
import time

import pandas as pd

# Plausible recent anchors (price, market cap, 24h % change) per asset.
_PROFILES = {
    # crypto
    "bitcoin": {"name": "Bitcoin", "symbol": "BTC", "price": 62000.0, "mcap": 1_220_000_000_000, "chg": 1.8, "vol": 0.018},
    "ethereum": {"name": "Ethereum", "symbol": "ETH", "price": 3050.0, "mcap": 366_000_000_000, "chg": -1.2, "vol": 0.025},
    "solana": {"name": "Solana", "symbol": "SOL", "price": 148.0, "mcap": 68_000_000_000, "chg": 3.4, "vol": 0.040},
    # stocks
    "AAPL": {"name": "Apple", "symbol": "AAPL", "price": 232.0, "mcap": 3_500_000_000_000, "chg": 0.9, "vol": 0.012},
    "TSLA": {"name": "Tesla", "symbol": "TSLA", "price": 248.0, "mcap": 790_000_000_000, "chg": -1.6, "vol": 0.030},
    "NVDA": {"name": "Nvidia", "symbol": "NVDA", "price": 132.0, "mcap": 3_200_000_000_000, "chg": 2.1, "vol": 0.025},
}

# Realistic, undated crypto headlines for the offline sentiment path.
MOCK_HEADLINES = [
    "Bitcoin ETF inflows surge as institutional demand climbs to record highs",
    "Ethereum upgrade boosts network throughput, developers signal optimism",
    "Solana ecosystem rallies on new stablecoin partnership",
    "Analysts warn of short-term volatility despite strong on-chain fundamentals",
    "Regulators outline clearer framework for digital asset custody",
    "Crypto market steadies after week of choppy trading",
]

# Offline finance headlines for stocks sentiment.
MOCK_STOCK_HEADLINES = [
    "Tech megacaps lead market higher as earnings beat expectations",
    "Analysts raise price targets citing strong AI-driven demand",
    "Investors weigh interest-rate path ahead of inflation data",
    "Profit-taking trims gains after a strong quarterly rally",
    "Supply-chain improvements boost hardware margins, firm says",
    "Markets steady as traders await guidance from the Federal Reserve",
]


def _build_ohlc(asset_id: str, points: int = 180):
    """Deterministic OHLC random-walk ending near the profile's anchor price."""
    p = _PROFILES[asset_id]
    rng = random.Random(hash(asset_id) & 0xFFFF)
    # Walk backwards from the anchor price so the latest close matches `price`.
    closes = [p["price"]]
    for _ in range(points - 1):
        drift = rng.uniform(-p["vol"], p["vol"])
        closes.append(closes[-1] / (1 + drift))
    closes.reverse()

    now_ms = int(time.time() * 1000)
    step = 4 * 60 * 60 * 1000  # 4 hours
    rows = []
    for i, close in enumerate(closes):
        prev = closes[i - 1] if i > 0 else close
        high = max(prev, close) * (1 + abs(rng.uniform(0, p["vol"] / 2)))
        low = min(prev, close) * (1 - abs(rng.uniform(0, p["vol"] / 2)))
        rows.append(
            {
                "timestamp": now_ms - (points - 1 - i) * step,
                "open": prev,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return pd.DataFrame(rows)


# Baked-in Fear & Greed reading for offline mode (0=extreme fear, 100=greed).
MOCK_FEAR_GREED = {"value": 64, "classification": "Greed"}


def mock_market_data(asset_id: str) -> dict:
    """Full market_data payload matching the live agent's shape."""
    p = _PROFILES.get(asset_id, _PROFILES["bitcoin"])
    df = _build_ohlc(asset_id if asset_id in _PROFILES else "bitcoin")
    return {
        "asset_id": asset_id,
        "name": p["name"],
        "symbol": p["symbol"],
        "current_price": p["price"],
        "market_cap": p["mcap"],
        "price_change_24h": p["chg"],
        "history": df,
        "source": "mock",
        "notice": "Mock mode — running on baked-in offline data.",
    }
