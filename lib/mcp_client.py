"""
MCP client — the orchestrator's link to the data servers.

Connects to the FastMCP servers over stdio (the pattern from the workshop
notebook: StdioServerParameters -> stdio_client -> ClientSession -> call_tool),
calls their tools, and records every call in a shared log so the UI can show
"MCP tools fired" live.

The whole crypto pipeline is synchronous, so we expose sync wrappers that run
the async MCP calls in a dedicated event-loop thread (safe whether or not an
event loop is already running, e.g. inside Streamlit).
"""

import asyncio
import json
import os
import sys
import threading
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_servers"))

# Logical server key -> server script. Adding a data source = one line here.
SERVERS = {
    "market": os.path.join(_SERVERS_DIR, "market_server.py"),
    "news": os.path.join(_SERVERS_DIR, "news_server.py"),
    "fear_greed": os.path.join(_SERVERS_DIR, "fear_greed_server.py"),
    "stocks": os.path.join(_SERVERS_DIR, "stocks_server.py"),
}

# ---------------------------------------------------------------------------
# Shared MCP call log — every tool invocation is appended here so the dashboard
# and CLI can display the live "MCP tools fired" trail.
# ---------------------------------------------------------------------------
_MCP_LOG: list[dict] = []


def reset_mcp_log():
    _MCP_LOG.clear()


def get_mcp_log() -> list[dict]:
    return list(_MCP_LOG)


def _server_params(server_key: str) -> StdioServerParameters:
    script = SERVERS[server_key]
    # Pass the full environment through so MOCK_MODE / USE_MCP reach the server
    # subprocess (lets MCP tools fire even in fully-offline mock mode).
    return StdioServerParameters(command=sys.executable, args=[script], env=os.environ.copy())


async def _call_many_async(server_key: str, calls: list[tuple]) -> dict:
    """Open ONE session to a server and call several tools on it."""
    params = _server_params(server_key)
    results = {}
    with open(os.devnull, "w") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for tool_name, args in calls:
                    started = time.time()
                    try:
                        res = await session.call_tool(tool_name, args)
                        text = "\n".join(
                            item.text if hasattr(item, "text") else str(item)
                            for item in res.content
                        )
                        results[tool_name] = text
                        _MCP_LOG.append({
                            "server": server_key, "tool": tool_name,
                            "status": "ok", "ms": int((time.time() - started) * 1000),
                        })
                    except Exception as exc:
                        results[tool_name] = None
                        _MCP_LOG.append({
                            "server": server_key, "tool": tool_name,
                            "status": "failed", "ms": int((time.time() - started) * 1000),
                            "error": str(exc)[:120],
                        })
    return results


# ---------------------------------------------------------------------------
# Sync bridge: run a coroutine to completion on a private event-loop thread.
# ---------------------------------------------------------------------------
def _run_sync(coro):
    box = {}

    def runner():
        loop = asyncio.new_event_loop()
        try:
            box["result"] = loop.run_until_complete(coro)
        except Exception as exc:  # connection refused, server crash, timeout...
            box["error"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["result"]


def call_tools(server_key: str, calls: list[tuple]) -> dict:
    """Sync: call multiple tools on one server in a single session.
    `calls` is a list of (tool_name, args_dict). Returns {tool_name: text|None}.
    On a connection-level failure, logs each requested tool as failed and
    returns Nones so callers can fall back gracefully."""
    try:
        return _run_sync(_call_many_async(server_key, calls))
    except Exception as exc:
        for tool_name, _ in calls:
            _MCP_LOG.append({"server": server_key, "tool": tool_name,
                             "status": "failed", "ms": 0, "error": str(exc)[:120]})
        return {tool_name: None for tool_name, _ in calls}


def call_tool(server_key: str, tool_name: str, args: dict = None):
    """Sync: call a single MCP tool. Returns the text result, or None on failure."""
    return call_tools(server_key, [(tool_name, args or {})]).get(tool_name)


def call_json(server_key: str, tool_name: str, args: dict = None):
    """call_tool + JSON parse. Returns parsed object, or None on any failure."""
    raw = call_tool(server_key, tool_name, args)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    # Smoke test: fire one tool on each server through the MCP client.
    reset_mcp_log()
    print("price:", call_json("market", "get_price", {"coin_id": "bitcoin"}))
    print("ohlc rows:", len(call_json("market", "get_ohlc_history", {"coin_id": "bitcoin", "days": 30}) or []))
    print("headlines:", (call_json("news", "get_headlines", {"limit": 3}) or [])[:1])
    print("fear_greed:", call_json("fear_greed", "get_fear_greed"))
    print("MCP log:", get_mcp_log())
