"""
Portfolio Manager Agent
=======================
Convenes the final **Investment Committee** — Bull, Bear, Risk Manager, Quant —
which debates the upstream verdicts and votes the final BUY / SELL / HOLD.

Confidence is COMPUTED, not hardcoded:

    base       = mean confidence of the committee members who voted for the verdict
    agreement  = (members backing the verdict) / 4
    confidence = base * (0.5 + 0.5 * agreement)        # more agreement -> higher
                 * 0.90 if risk level is High           # volatility haircut
                 * 0.92 if upstream data trust is weak   # bad-data haircut

`combined_score` (technicals 0.6 / sentiment 0.4) is kept as the systematic
Quant signal that seeds the debate.
"""

from lib.debate import member, make_panel

TECH_WEIGHT = 0.6
SENT_WEIGHT = 0.4
THRESHOLD = 0.15


def make_final_decision(technical_result, sentiment_result, risk_result, market_data=None):
    tech_signal = technical_result["signal"]
    strength = technical_result.get("strength", 0)
    sent = sentiment_result["sentiment"]
    sent_vote = sentiment_result.get("vote", 0)
    sent_score = sentiment_result.get("score", 50)
    risk_level = risk_result.get("risk_level", "Medium")
    data_trust = ((market_data or {}).get("panel") or {}).get("verdict", "GOOD")

    tech_dir = 1 if tech_signal == "BUY" else (-1 if tech_signal == "SELL" else 0)
    combined = TECH_WEIGHT * (tech_dir * strength / 100.0) + SENT_WEIGHT * (sent_vote * abs(sent_score - 50) / 50.0)
    quant_stance = "BUY" if combined > THRESHOLD else ("SELL" if combined < -THRESHOLD else "HOLD")

    bullish = tech_signal == "BUY" or sent == "Positive"
    bearish = tech_signal == "SELL" or sent == "Negative"
    conflict = (tech_dir > 0 and sent_vote < 0) or (tech_dir < 0 and sent_vote > 0)

    members = []
    # Bull
    if bullish and not bearish:
        members.append(member("Bull Analyst", "BUY", 55 + strength // 3, f"Technicals {tech_signal} and/or {sent.lower()} sentiment back upside."))
    else:
        members.append(member("Bull Analyst", "HOLD", 50, "Not enough bullish confirmation to commit."))
    # Bear
    if bearish and not bullish:
        members.append(member("Bear Analyst", "SELL", 55 + strength // 3, f"Technicals {tech_signal} and/or {sent.lower()} sentiment warn of downside."))
    else:
        members.append(member("Bear Analyst", "HOLD", 50, "No clear breakdown — staying flat."))
    # Risk Manager
    if risk_level == "High" or conflict:
        members.append(member("Risk Manager", "HOLD", 64, "High risk or conflicting signals — protect capital, wait."))
    else:
        members.append(member("Risk Manager", tech_signal, 58, f"Risk is {risk_level.lower()} and signals align — comfortable with {tech_signal}."))
    # Quant
    members.append(member("Quant", quant_stance, 50 + round(abs(combined) * 50),
                          f"Systematic score {combined:+.2f} (0.6·tech + 0.4·sentiment) -> {quant_stance}."))

    panel = make_panel("Investment Committee", members, neutral="HOLD")
    final_decision = panel["verdict"]

    # ---- computed confidence -------------------------------------------
    winners = sum(1 for m in members if m["stance"] == final_decision)
    agreement = winners / 4.0
    confidence = panel["verdict_confidence"] * (0.5 + 0.5 * agreement)
    if risk_level == "High":
        confidence *= 0.90
    if data_trust in ("DEGRADED", "STALE"):
        confidence *= 0.92
    confidence = int(round(max(0, min(100, confidence))))

    agreement_txt = f"{winners}/4 committee agree" if final_decision != "HOLD" or winners > 1 else "split committee"
    summary = _summary(final_decision, tech_signal, sent, risk_level, agreement_txt, data_trust)

    return {
        "final_decision": final_decision, "confidence": confidence, "summary": summary,
        "combined_score": round(combined, 3), "agreement": agreement_txt,
        "votes": {"technical": tech_signal, "sentiment": sent, "risk": risk_level, "data_trust": data_trust},
        "panel": panel,
    }


def _summary(decision, tech_signal, sentiment, risk_level, agreement, data_trust):
    trust = "" if data_trust == "GOOD" else f" Data trust is {data_trust.lower()}, so confidence is trimmed."
    if decision == "HOLD":
        return (f"Holding — technical {tech_signal}, {sentiment.lower()} sentiment, {agreement}. "
                f"No high-conviction edge.{trust}")
    verb = "buying" if decision == "BUY" else "selling"
    return (f"Committee recommends {verb}: technical {tech_signal} + {sentiment.lower()} sentiment "
            f"({agreement}) at {risk_level.lower()} risk.{trust}")
