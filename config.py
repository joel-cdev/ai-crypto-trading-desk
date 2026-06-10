"""
Central configuration for the AI Crypto Trading Desk.

Keeps environment toggles and shared constants in one place so the CLI
(main.py) and the dashboard (dashboard/app.py) behave identically.
"""

import os


# ---------------------------------------------------------------------------
# Tradable universe. Two markets: crypto (CoinGecko ids) and stocks (tickers).
# ---------------------------------------------------------------------------
SUPPORTED_COINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
}

SUPPORTED_STOCKS = {
    "AAPL": "Apple",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
}

# Per-market asset universe + default, used by the CLI and dashboard selectors.
MARKETS = {
    "crypto": {"label": "Crypto", "assets": SUPPORTED_COINS, "default": "bitcoin"},
    "stocks": {"label": "Stocks", "assets": SUPPORTED_STOCKS, "default": "AAPL"},
}


def market_of(asset_id: str) -> str:
    """Infer which market an asset id belongs to (default crypto)."""
    return "stocks" if asset_id in SUPPORTED_STOCKS else "crypto"

# ---------------------------------------------------------------------------
# Network / API settings
# ---------------------------------------------------------------------------
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT = 8           # seconds — keep the live demo snappy, never hang
CACHE_TTL_SECONDS = 120       # short TTL so repeated demo runs don't hammer the API
HISTORY_DAYS = 30             # how much price history to pull for indicators

# CoinDesk RSS — free, no key required. Used by the sentiment agent.
NEWS_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"

# Crypto Fear & Greed Index — alternative.me, free, no key. The "distinctive
# edge" data source, exposed as its own MCP server.
FNG_URL = "https://api.alternative.me/fng/?limit=1"

# Yahoo Finance — free, no key. Stocks quotes/history + per-ticker news RSS.
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_NEWS_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"

# ---------------------------------------------------------------------------
# OpenAI model selection. gpt-4o-mini = fast/cheap default; override via env.
# ---------------------------------------------------------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def openai_enabled():
    """True only when an API key is present. Everything degrades to rule-based
    logic when this is False, so the demo always runs offline."""
    return bool(os.getenv("OPENAI_API_KEY"))


def use_mcp():
    """Whether agents should fetch data through the MCP servers (default on).
    Set USE_MCP=0 to bypass MCP and call the data sources directly."""
    return os.getenv("USE_MCP", "1").strip().lower() not in ("0", "false", "no", "off")


def mock_mode():
    """Global MOCK_MODE toggle (env var). The dashboard sidebar checkbox can
    also force this on per-session via set_mock_mode()."""
    return os.getenv("MOCK_MODE", "").strip().lower() in ("1", "true", "yes", "on")


_FORCED_MOCK = None


def set_mock_mode(value: bool):
    """Force mock mode on/off for the current process (used by the UI checkbox)."""
    global _FORCED_MOCK
    _FORCED_MOCK = value


def use_mock():
    """Resolved mock state: explicit UI override wins, otherwise the env var."""
    if _FORCED_MOCK is not None:
        return _FORCED_MOCK
    return mock_mode()
