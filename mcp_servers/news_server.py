"""
News MCP Server
===============
Exposes recent crypto headlines (CoinDesk RSS) as an MCP tool, so the Sentiment
agent gets its news by calling a tool over MCP — independent of price data.

Tool:
  * get_headlines(limit) -> recent crypto headline strings

Respects MOCK_MODE (returns baked-in headlines offline).

Run standalone:  python mcp_servers/news_server.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import feedparser
import requests
from mcp.server.fastmcp import FastMCP

from config import NEWS_RSS_URL, REQUEST_TIMEOUT, use_mock
from lib.mock_data import MOCK_HEADLINES

mcp = FastMCP("news-server")


@mcp.tool()
def get_headlines(limit: int = 8) -> str:
    """Get recent crypto news headlines from CoinDesk. Returns a JSON list of strings."""
    if use_mock():
        return json.dumps(list(MOCK_HEADLINES)[:limit])

    raw = requests.get(NEWS_RSS_URL, timeout=REQUEST_TIMEOUT,
                       headers={"User-Agent": "ai-crypto-trading-desk/1.0"})
    raw.raise_for_status()
    feed = feedparser.parse(raw.content)
    headlines = [e.title for e in feed.entries[:limit] if getattr(e, "title", None)]
    if not headlines:
        raise ValueError("No headlines returned")
    return json.dumps(headlines)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print(get_headlines(4))
    else:
        mcp.run()
