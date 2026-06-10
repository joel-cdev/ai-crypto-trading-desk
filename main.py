"""
CLI entry point. Runs the same 6-agent pipeline as the dashboard and prints a
report, including each agent's 4-member debate panel. Usage:

    python main.py [asset]               # bitcoin | ethereum | solana | AAPL | TSLA | NVDA
    python main.py AAPL --market stocks  # force stocks market
    MOCK_MODE=1 python main.py solana    # fully offline demo
"""

import sys

from config import SUPPORTED_COINS, SUPPORTED_STOCKS, market_of
from pipeline import run_pipeline, AGENTS


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asset = args[0] if args else "bitcoin"
    market = None
    if "--market" in sys.argv:
        market = sys.argv[sys.argv.index("--market") + 1]
    market = market or market_of(asset)

    valid = {**SUPPORTED_COINS, **SUPPORTED_STOCKS}
    if asset not in valid:
        print(f"Unknown asset '{asset}'. Choose from: {', '.join(valid)}")
        return

    print("AI Trading Desk — multi-agent debate pipeline")
    print("=" * 48)

    def on_step(index, key, state):
        if state == "running":
            print(f"  [{index + 1}/6] {AGENTS[index][1]} ...")

    results = run_pipeline(asset, on_step=on_step, market=market)

    market_data = results["market_data"]
    if market_data.get("notice"):
        print(f"\nNOTE: {market_data['notice']}")

    print()
    print(results["explanation"])

    # ---- debate panels --------------------------------------------------
    print("Debate panels (24 sub-agents)")
    print("-" * 28)
    for key, label in AGENTS:
        panel = results["panels"].get(key)
        if not panel:
            continue
        print(f"\n{panel['title']}  ->  {panel['verdict']} ({panel['verdict_confidence']}%)  {panel['tally']}")
        for m in panel["members"]:
            print(f"   - {m['name']:<24} {m['stance']:<9} {m['confidence']:>3}%  {m['rationale']}")

    port = results["portfolio"]
    print("\nFinal Decision:", port["final_decision"], "| Confidence:", f"{port['confidence']}% (computed)")
    print("Votes:", port["votes"])

    print("\nMCP Tools Fired")
    print("-" * 28)
    for c in results.get("mcp_log", []) or [("none",)]:
        if isinstance(c, dict):
            print(f"[{'ok ' if c['status'] == 'ok' else 'FAIL'}] {c['server']}.{c['tool']}  ({c['ms']}ms)")
        else:
            print("(none — MCP disabled or served from cache)")


if __name__ == "__main__":
    main()
