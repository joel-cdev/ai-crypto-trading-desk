"""
Risk Management Agent
=====================
Sizes the stop-loss / target from real volatility (ATR), then convenes a
4-member **Risk Committee** that debates the risk grade:

  * ATR Sizer        — absolute volatility (ATR % of price)
  * Reward:Risk      — is the payoff geometry favourable?
  * Stop-Distance    — how far the stop sits (tight vs wide)
  * Exposure Advisor — overall position caution

The committee verdict (Low / Medium / High) is the agent's risk level.
"""

from lib import indicators
from lib.debate import member, make_panel

STOP_MULT = 1.5
TARGET_MULT = 2.5
FIXED_STOP_PCT = 0.02
FIXED_TARGET_PCT = 0.03


def calculate_risk(market_data, technical_result):
    price = market_data["current_price"]
    signal = technical_result["signal"]
    history = market_data.get("history")

    if history is not None and len(history) >= 15:
        atr_val = indicators.atr(history, period=14)
        atr_pct = atr_val / price * 100 if price else 0.0
        stop_dist, target_dist = STOP_MULT * atr_val, TARGET_MULT * atr_val
        method = "atr"
    else:
        atr_val = None
        atr_pct = FIXED_STOP_PCT * 100
        stop_dist, target_dist = price * FIXED_STOP_PCT, price * FIXED_TARGET_PCT
        method = "fixed"

    if signal == "BUY":
        entry_price, target_price, stop_loss = price, price + target_dist, price - stop_dist
    elif signal == "SELL":
        entry_price, target_price, stop_loss = price, price - target_dist, price + stop_dist
    else:
        entry_price, target_price, stop_loss = price, None, None

    reward_risk = round(TARGET_MULT / STOP_MULT, 2) if method == "atr" else round(FIXED_TARGET_PCT / FIXED_STOP_PCT, 2)
    stop_pct = stop_dist / price * 100 if price else 0.0

    # ---- Risk Committee ------------------------------------------------
    members = []
    # ATR Sizer
    if atr_pct < 1.5:
        members.append(member("ATR Sizer", "Low", 80, f"ATR {atr_pct:.1f}% of price — calm market."))
    elif atr_pct < 4.0:
        members.append(member("ATR Sizer", "Medium", 70, f"ATR {atr_pct:.1f}% of price — normal volatility."))
    else:
        members.append(member("ATR Sizer", "High", 78, f"ATR {atr_pct:.1f}% of price — choppy, size down."))
    # Reward:Risk
    if reward_risk >= 1.5:
        members.append(member("Reward:Risk", "Low", 72, f"Payoff {reward_risk}:1 is favourable."))
    elif reward_risk >= 1.0:
        members.append(member("Reward:Risk", "Medium", 60, f"Payoff {reward_risk}:1 is borderline."))
    else:
        members.append(member("Reward:Risk", "High", 70, f"Payoff {reward_risk}:1 is poor."))
    # Stop distance
    if signal == "HOLD":
        members.append(member("Stop-Distance", "Low", 65, "No active trade — no stop at risk."))
    elif stop_pct < 2:
        members.append(member("Stop-Distance", "Medium", 58, f"Stop {stop_pct:.1f}% away — tight, watch for whipsaw."))
    elif stop_pct < 6:
        members.append(member("Stop-Distance", "Low", 66, f"Stop {stop_pct:.1f}% away — reasonable room."))
    else:
        members.append(member("Stop-Distance", "High", 64, f"Stop {stop_pct:.1f}% away — wide, larger loss if hit."))
    # Exposure
    if signal == "HOLD":
        members.append(member("Exposure Advisor", "Low", 70, "Recommending no position — minimal exposure."))
    elif atr_pct >= 4.0:
        members.append(member("Exposure Advisor", "High", 68, "High volatility — keep position small."))
    else:
        members.append(member("Exposure Advisor", "Medium", 60, "Standard exposure with the computed stop."))

    panel = make_panel("Risk Committee", members, neutral="Medium")
    risk_level = "Low" if signal == "HOLD" else panel["verdict"]

    return {
        "entry_price": entry_price, "target_price": target_price, "stop_loss": stop_loss,
        "risk_level": risk_level, "atr": round(atr_val, 2) if atr_val is not None else None,
        "atr_pct": round(atr_pct, 2), "reward_risk": reward_risk, "method": method, "panel": panel,
    }
