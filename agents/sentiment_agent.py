"""
Sentiment Agent
===============
Price-independent. Convenes a 4-member **Sentiment Desk**:

  * News Analyst        — headlines (CoinDesk for crypto / Yahoo per-ticker for stocks),
                          classified via OpenAI (keyword fallback)
  * Fear & Greed Analyst (crypto)  — Crypto Fear & Greed Index  [the distinctive edge]
    Market-Mood Analyst (stocks)   — no equity F&G index, votes neutral
  * Keyword-Momentum Analyst — bullish vs bearish keyword tilt
  * Contrarian Analyst       — fades extreme greed / fear

Headlines + F&G are fetched as MCP tools. Final 0-100 score blends them
(crypto: 0.6·news + 0.4·F&G; stocks: news only). The panel vote gives the
Positive/Neutral/Negative label.
"""

import feedparser

from config import NEWS_RSS_URL, YAHOO_NEWS_RSS, FNG_URL, REQUEST_TIMEOUT, use_mock, use_mcp
from lib import mcp_client
from lib.llm import chat_json
from lib.debate import member, make_panel
from lib.mock_data import MOCK_HEADLINES, MOCK_STOCK_HEADLINES, MOCK_FEAR_GREED

NEWS_WEIGHT = 0.6
FNG_WEIGHT = 0.4

_POSITIVE_WORDS = ["surge", "soar", "rally", "gain", "record", "high", "boost", "bullish",
                   "optimism", "inflow", "adoption", "approval", "partnership", "upgrade", "growth", "beat"]
_NEGATIVE_WORDS = ["crash", "plunge", "drop", "fall", "selloff", "bearish", "fear", "hack",
                   "ban", "lawsuit", "fraud", "outflow", "warning", "volatility", "decline", "risk", "miss"]


def _fetch_headlines(market, asset_id, limit=8):
    if market == "stocks":
        if use_mcp():  # stocks headlines aren't an MCP tool; fetch via Yahoo RSS directly
            pass
        if use_mock():
            return list(MOCK_STOCK_HEADLINES)[:limit], "mock"
        try:
            import requests
            raw = requests.get(YAHOO_NEWS_RSS.format(symbol=asset_id), timeout=REQUEST_TIMEOUT,
                               headers={"User-Agent": "Mozilla/5.0"})
            raw.raise_for_status()
            feed = feedparser.parse(raw.content)
            hl = [e.title for e in feed.entries[:limit] if getattr(e, "title", None)]
            if hl:
                return hl, "yahoo"
        except Exception:
            pass
        return list(MOCK_STOCK_HEADLINES)[:limit], "fallback"

    # crypto
    if use_mcp():
        data = mcp_client.call_json("news", "get_headlines", {"limit": limit})
        if data:
            return data, "mcp"
    if use_mock():
        return list(MOCK_HEADLINES)[:limit], "mock"
    try:
        import requests
        raw = requests.get(NEWS_RSS_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "ai-crypto-trading-desk/1.0"})
        raw.raise_for_status()
        feed = feedparser.parse(raw.content)
        hl = [e.title for e in feed.entries[:limit] if getattr(e, "title", None)]
        if hl:
            return hl, "direct"
    except Exception:
        pass
    return list(MOCK_HEADLINES)[:limit], "fallback"


def _fetch_fear_greed(market):
    if market != "crypto":
        return None  # no equity Fear & Greed index in this demo
    if use_mcp():
        data = mcp_client.call_json("fear_greed", "get_fear_greed")
        if data:
            return data
    if use_mock():
        return dict(MOCK_FEAR_GREED)
    try:
        import requests
        resp = requests.get(FNG_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "ai-crypto-trading-desk/1.0"})
        resp.raise_for_status()
        item = resp.json()["data"][0]
        return {"value": int(item["value"]), "classification": item["value_classification"]}
    except Exception:
        return None


def _keyword_score(headlines):
    pos = neg = 0
    text = " ".join(headlines).lower()
    for w in _POSITIVE_WORDS:
        pos += text.count(w)
    for w in _NEGATIVE_WORDS:
        neg += text.count(w)
    total = pos + neg
    if total == 0:
        return 50, pos, neg
    raw = pos / total
    conviction = total / (total + 4)
    return round(50 + (raw * 100 - 50) * conviction), pos, neg


def _llm_score(headlines):
    system = ("You are a market sentiment analyst. Judge the OVERALL mood of these headlines. "
              'Respond JSON only: {"score": <0-100 int>, "reason": "<one sentence>"}. 0=very bearish, 100=very bullish.')
    data = chat_json(system, "Headlines:\n" + "\n".join(f"- {h}" for h in headlines), max_tokens=160)
    if not data:
        return None
    try:
        return max(0, min(100, int(round(float(data["score"]))))), str(data.get("reason", "")).strip()
    except (KeyError, ValueError, TypeError):
        return None


def _label(score):
    return "Positive" if score >= 60 else ("Negative" if score <= 40 else "Neutral")


def analyze_sentiment(market_data=None):
    market = (market_data or {}).get("market", "crypto")
    asset_id = (market_data or {}).get("asset_id", "bitcoin")

    before = len(mcp_client.get_mcp_log())
    headlines, feed_source = _fetch_headlines(market, asset_id)
    fng = _fetch_fear_greed(market)
    mcp_calls = mcp_client.get_mcp_log()[before:]

    llm = _llm_score(headlines)
    if llm is not None:
        news_score, news_reason = llm
        method = "openai"
    else:
        kw, pos, neg = _keyword_score(headlines)
        news_score, news_reason = kw, f"{pos} bullish vs {neg} bearish terms"
        method = "keyword"

    kw_score, kpos, kneg = _keyword_score(headlines)

    # ---- 4-member Sentiment Desk ---------------------------------------
    members = []
    members.append(member("News Analyst", _label(news_score), 50 + abs(news_score - 50),
                          f"Headlines read {news_score}/100 ({news_reason})."))

    if fng is not None:
        members.append(member("Fear & Greed Analyst", _label(fng["value"]), 50 + abs(fng["value"] - 50),
                              f"Index at {fng['value']}/100 — {fng['classification']}."))
    else:
        members.append(member("Market-Mood Analyst", "Neutral", 45,
                              "No equity Fear & Greed index — deferring to news."))

    members.append(member("Keyword-Momentum Analyst", _label(kw_score), 50 + abs(kw_score - 50),
                          f"Keyword tilt {kpos} bullish / {kneg} bearish terms."))

    # Contrarian: fade extremes (crypto F&G if present, else news extreme)
    gauge = fng["value"] if fng is not None else news_score
    if gauge >= 75:
        members.append(member("Contrarian Analyst", "Negative", 60, f"Crowd extremely greedy ({gauge}) — fade the euphoria."))
    elif gauge <= 25:
        members.append(member("Contrarian Analyst", "Positive", 60, f"Crowd extremely fearful ({gauge}) — fade the panic."))
    else:
        members.append(member("Contrarian Analyst", "Neutral", 48, f"Crowd not at an extreme ({gauge}) — nothing to fade."))

    panel = make_panel("Sentiment Desk", members, neutral="Neutral")

    # ---- blended numeric score for the portfolio agent -----------------
    if fng is not None:
        score = round(NEWS_WEIGHT * news_score + FNG_WEIGHT * fng["value"])
        reason = f"News {news_score}/100 ({news_reason}); Fear & Greed {fng['value']}/100 ({fng['classification']})."
    else:
        score = news_score
        reason = f"News {news_score}/100 ({news_reason}); no equity Fear & Greed index."

    sentiment = panel["verdict"]
    vote = 1 if sentiment == "Positive" else (-1 if sentiment == "Negative" else 0)

    return {
        "sentiment": sentiment, "score": score, "reason": reason, "vote": vote,
        "headlines": headlines, "method": method, "feed_source": feed_source,
        "fear_greed": fng, "news_score": news_score, "mcp_calls": mcp_calls, "panel": panel,
    }
