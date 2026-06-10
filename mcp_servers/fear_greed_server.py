"""
Fear & Greed MCP Server  (the distinctive edge)
==============================================
Exposes the Crypto Fear & Greed Index (alternative.me, free, no key) as an MCP
tool. This is an aggregate market-mood signal — volatility, momentum, social,
dominance — that most BTC/ETH/SOL demos don't use, giving the Sentiment agent a
second, richer, price-independent input.

Tool:
  * get_fear_greed() -> {value 0-100, classification}

Respects MOCK_MODE (returns a baked-in reading offline).

Run standalone:  python mcp_servers/fear_greed_server.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from mcp.server.fastmcp import FastMCP

from config import FNG_URL, REQUEST_TIMEOUT, use_mock
from lib.mock_data import MOCK_FEAR_GREED

mcp = FastMCP("fear-greed-server")


@mcp.tool()
def get_fear_greed() -> str:
    """Get the current Crypto Fear & Greed Index.
    Returns JSON {value: 0-100 (0=extreme fear, 100=extreme greed), classification}."""
    if use_mock():
        return json.dumps(MOCK_FEAR_GREED)

    resp = requests.get(FNG_URL, timeout=REQUEST_TIMEOUT,
                        headers={"User-Agent": "ai-crypto-trading-desk/1.0"})
    resp.raise_for_status()
    item = resp.json()["data"][0]
    return json.dumps({
        "value": int(item["value"]),
        "classification": item["value_classification"],
    })


if __name__ == "__main__":
    if "--test" in sys.argv:
        print(get_fear_greed())
    else:
        mcp.run()
