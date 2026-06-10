"""
Technical Analysis Agent
========================
Convenes a 4-member **Technical Desk** that debates the chart:

  * RSI Analyst         — momentum / overbought-oversold (RSI 14)
  * MACD Analyst        — trend + momentum confirmation (MACD 12/26/9)
  * Trend Analyst       — 10 vs 30 moving-average crossover
  * Momentum Analyst    — 10-bar rate of change

Each casts a BUY/SELL/HOLD stance with a computed confidence; the panel vote is
the agent's signal and its verdict confidence is the signal `strength`.
All indicator values come from `lib/indicators.py` — real math, no guesses.
"""

from lib import indicators
from lib.debate import member, make_panel


def analyze_price_change(market_data):
    history = market_data.get("history")
    price = market_data["current_price"]

    if history is None or len(history) < 35:
        return _fallback(market_data)

    close = history["close"]
    rsi_val = indicators.rsi(close, period=14)
    ma_fast, ma_slow = indicators.moving_averages(close, fast=10, slow=30)
    macd_line, signal_line, macd_hist = indicators.macd(close)
    roc = (close.iloc[-1] / close.iloc[-11] - 1) * 100 if len(close) > 11 else 0.0
    ma_gap = (ma_fast - ma_slow) / ma_slow * 100 if ma_slow else 0.0

    members = []
    # RSI
    if rsi_val < 30:
        members.append(member("RSI Analyst", "BUY", min(95, 55 + (30 - rsi_val) * 2), f"RSI {rsi_val:.1f} is oversold — bounce likely."))
    elif rsi_val > 70:
        members.append(member("RSI Analyst", "SELL", min(95, 55 + (rsi_val - 70) * 2), f"RSI {rsi_val:.1f} is overbought — pullback risk."))
    else:
        members.append(member("RSI Analyst", "HOLD", 50 + int(abs(rsi_val - 50) / 2), f"RSI {rsi_val:.1f} is neutral — no edge."))
    # MACD
    if macd_hist > 0:
        members.append(member("MACD Analyst", "BUY", 62 + min(28, abs(macd_hist) / max(abs(macd_line), 1) * 40), "MACD histogram positive — momentum building."))
    elif macd_hist < 0:
        members.append(member("MACD Analyst", "SELL", 62 + min(28, abs(macd_hist) / max(abs(macd_line), 1) * 40), "MACD histogram negative — momentum fading."))
    else:
        members.append(member("MACD Analyst", "HOLD", 50, "MACD flat — momentum balanced."))
    # Trend (MA)
    if ma_fast > ma_slow:
        members.append(member("Trend Analyst", "BUY", min(95, 58 + abs(ma_gap) * 4), f"10-MA above 30-MA by {ma_gap:.2f}% — uptrend."))
    elif ma_fast < ma_slow:
        members.append(member("Trend Analyst", "SELL", min(95, 58 + abs(ma_gap) * 4), f"10-MA below 30-MA by {abs(ma_gap):.2f}% — downtrend."))
    else:
        members.append(member("Trend Analyst", "HOLD", 50, "Moving averages flat — no trend."))
    # Momentum (ROC)
    if roc > 0.5:
        members.append(member("Momentum Analyst", "BUY", min(95, 55 + abs(roc) * 3), f"10-bar momentum +{roc:.1f}% — pushing higher."))
    elif roc < -0.5:
        members.append(member("Momentum Analyst", "SELL", min(95, 55 + abs(roc) * 3), f"10-bar momentum {roc:.1f}% — pushing lower."))
    else:
        members.append(member("Momentum Analyst", "HOLD", 52, f"10-bar momentum flat ({roc:.1f}%)."))

    panel = make_panel("Technical Desk", members, neutral="HOLD")
    signal = panel["verdict"]
    strength = panel["verdict_confidence"]
    votes = {"rsi": _v(members[0]), "macd": _v(members[1]), "ma": _v(members[2]), "momentum": _v(members[3])}

    return {
        "signal": signal,
        "strength": strength,
        "reason": f"Desk vote {panel['tally']} -> {signal}. " + members[0]["rationale"] + " " + members[2]["rationale"],
        "votes": votes,
        "indicators": {
            "rsi": round(rsi_val, 1), "ma_fast": round(ma_fast, 2), "ma_slow": round(ma_slow, 2),
            "macd": round(macd_line, 2), "macd_signal": round(signal_line, 2),
            "macd_hist": round(macd_hist, 2), "roc": round(roc, 2),
        },
        "price": price,
        "panel": panel,
    }


def _v(m):
    return 1 if m["stance"] == "BUY" else (-1 if m["stance"] == "SELL" else 0)


def _fallback(market_data):
    change = market_data.get("price_change_24h", 0.0)
    signal = "BUY" if change > 2 else ("SELL" if change < -2 else "HOLD")
    m = [member("24h Change", signal, 40, f"History unavailable — using 24h change {change:.2f}%.")] * 1
    members = [
        member("RSI Analyst", "HOLD", 40, "No history for RSI."),
        member("MACD Analyst", "HOLD", 40, "No history for MACD."),
        member("Trend Analyst", signal, 45, f"Only 24h change available ({change:.2f}%)."),
        member("Momentum Analyst", signal, 45, f"24h change {change:.2f}%."),
    ]
    panel = make_panel("Technical Desk", members, neutral="HOLD")
    return {
        "signal": panel["verdict"], "strength": panel["verdict_confidence"],
        "reason": f"Price history unavailable — using 24h change ({change:.2f}%) only.",
        "votes": {"rsi": 0, "macd": 0, "ma": _v(members[2]), "momentum": _v(members[3])},
        "indicators": None, "price": market_data["current_price"], "panel": panel,
    }
