"""
Agent pipeline orchestration.

Single source of truth for the order the 6 agents run in, used by BOTH the CLI
(main.py) and the dashboard (dashboard/app.py) so they stay consistent.

Every agent convenes a 4-member debate panel (see lib/debate.py); the 6 panels
are collected and a single batched LLM call narrates all 24 sub-agents at once.

`run_pipeline` accepts an optional `on_step` callback so the UI can light up
each agent as it moves pending -> running -> done.
"""

from agents.market_data_agent import get_market_data
from agents.technical_agent import analyze_price_change
from agents.sentiment_agent import analyze_sentiment
from agents.risk_agent import calculate_risk
from agents.portfolio_agent import make_final_decision
from agents.explanation_agent import create_explanation
from lib import mcp_client, debate
from config import market_of

# (key, label) for each pipeline stage, in execution order.
AGENTS = [
    ("market", "Market Data Agent"),
    ("technical", "Technical Analysis Agent"),
    ("sentiment", "Sentiment Agent"),
    ("risk", "Risk Management Agent"),
    ("portfolio", "Portfolio Manager Agent"),
    ("explanation", "Explanation Agent"),
]


def run_pipeline(asset_id="bitcoin", on_step=None, market_data=None, market=None):
    """Run all six agents in order; return a dict of their results + panels."""
    market = market or market_of(asset_id)
    mcp_client.reset_mcp_log()

    def step(index, key, fn):
        if on_step:
            on_step(index, key, "running")
        result = fn()
        if on_step:
            on_step(index, key, "done")
        return result

    market_data = step(0, "market",
                       lambda: market_data if market_data is not None
                       else get_market_data(asset_id, market))
    technical = step(1, "technical", lambda: analyze_price_change(market_data))
    sentiment = step(2, "sentiment", lambda: analyze_sentiment(market_data))
    risk = step(3, "risk", lambda: calculate_risk(market_data, technical))
    portfolio = step(4, "portfolio",
                     lambda: make_final_decision(technical, sentiment, risk, market_data))
    explanation = step(5, "explanation",
                       lambda: create_explanation(market_data, technical, risk, portfolio, sentiment))

    # Collect the 6 debate panels and narrate every sub-agent in ONE batched call.
    panels = {
        "market": market_data.get("panel"),
        "technical": technical.get("panel"),
        "sentiment": sentiment.get("panel"),
        "risk": risk.get("panel"),
        "portfolio": portfolio.get("panel"),
        "explanation": explanation.get("panel"),
    }
    panels = {k: v for k, v in panels.items() if v}
    context = (f"{market_data['name']} ({market_data['symbol']}) {market} | price "
               f"${market_data['current_price']:,.2f} | 24h {market_data['price_change_24h']:.2f}% | "
               f"decision {portfolio['final_decision']} {portfolio['confidence']}%")
    debate.narrate_all(panels, context)

    mcp_log = list(market_data.get("mcp_calls", [])) + list(sentiment.get("mcp_calls", []))

    return {
        "market_data": market_data,
        "technical": technical,
        "sentiment": sentiment,
        "risk": risk,
        "portfolio": portfolio,
        "explanation": explanation["text"],
        "panels": panels,
        "mcp_log": mcp_log,
    }
