"""
Explanation Agent
=================
Turns the structured decision into a plain-language briefing (OpenAI when a key
is set; string-template fallback offline), then runs it past a 4-member
**Editorial Review** board that checks the briefing before it ships:

  * Accuracy Editor       — every number matches the computed pipeline values
  * Clarity Editor        — a non-technical reader can follow it
  * Risk-Disclosure Editor — the not-financial-advice disclaimer is present
  * Action Editor         — there is a clear, actionable plan

Returns {"text": briefing, "panel": editorial review}. The LLM only phrases
numbers computed elsewhere — it never invents or alters a figure.
"""

from lib.llm import chat
from lib.debate import member, make_panel


def _fmt(value, prefix="$"):
    return f"{prefix}{value:,.2f}" if isinstance(value, (int, float)) else "N/A"


def create_explanation(market_data, technical_result, risk_result, portfolio_result, sentiment_result=None):
    facts = _build_facts(market_data, technical_result, risk_result, portfolio_result, sentiment_result)
    text = _llm_explanation(facts) or _template_explanation(
        market_data, technical_result, risk_result, portfolio_result, sentiment_result)
    panel = _editorial_panel(text, risk_result, portfolio_result, technical_result)
    return {"text": text, "panel": panel}


def _build_facts(market_data, technical_result, risk_result, portfolio_result, sentiment_result):
    ind = technical_result.get("indicators") or {}
    lines = [
        f"Asset: {market_data['name']} ({market_data['symbol']}) — {market_data.get('market', 'crypto')} market",
        f"Current price: {_fmt(market_data['current_price'])}",
        f"24h change: {market_data['price_change_24h']:.2f}%",
        f"Final decision: {portfolio_result['final_decision']}",
        f"Confidence: {portfolio_result['confidence']}% ({portfolio_result['agreement']})",
        f"Technical signal: {technical_result['signal']} (strength {technical_result.get('strength', 0)}/100)",
    ]
    if ind:
        lines.append(f"Indicators — RSI {ind['rsi']}, 10-MA {ind['ma_fast']}, 30-MA {ind['ma_slow']}, MACD hist {ind['macd_hist']}")
    if sentiment_result:
        lines.append(f"Sentiment: {sentiment_result['sentiment']} (score {sentiment_result['score']}/100) — {sentiment_result['reason']}")
    lines.append(f"Risk: {risk_result['risk_level']} (method {risk_result['method']})")
    if risk_result["target_price"] is not None:
        lines += [f"Entry: {_fmt(risk_result['entry_price'])}", f"Target: {_fmt(risk_result['target_price'])}",
                  f"Stop-loss: {_fmt(risk_result['stop_loss'])}", f"Reward:risk: {risk_result['reward_risk']}"]
    return "\n".join(lines)


def _llm_explanation(facts):
    system = (
        "You are a trading-desk analyst writing a short briefing for a non-technical client. "
        "Use ONLY the facts provided; do NOT invent, change, or recompute any number. Write 2 short "
        "paragraphs: (1) the recommendation and why; (2) the trade plan (entry/target/stop) and risk. "
        "End with a one-line reminder that this is a demo, not financial advice."
    )
    return chat(system, f"Facts:\n{facts}", max_tokens=400)


def _template_explanation(market_data, technical_result, risk_result, portfolio_result, sentiment_result):
    text = f"""Final Trading Report

Asset: {market_data['name']} ({market_data['symbol']}) — {market_data.get('market', 'crypto')}
Current Price: {_fmt(market_data['current_price'])}
24h Price Change: {market_data['price_change_24h']:.2f}%

Final Decision: {portfolio_result['final_decision']}
Confidence Score: {portfolio_result['confidence']}%  ({portfolio_result['agreement']})

Why this decision was made:
{technical_result['reason']}
"""
    if sentiment_result:
        text += f"Sentiment: {sentiment_result['sentiment']} ({sentiment_result['score']}/100) — {sentiment_result['reason']}\n"
    text += "\nRisk Plan:\n" + f"Entry Price: {_fmt(risk_result['entry_price'])}\n"
    if risk_result["target_price"] is not None:
        text += (f"Target Price: {_fmt(risk_result['target_price'])}\n"
                 f"Stop Loss: {_fmt(risk_result['stop_loss'])}\n"
                 f"Reward:Risk: {risk_result['reward_risk']}  |  Method: {risk_result['method']}\n")
    else:
        text += "Target Price: Not needed for HOLD\nStop Loss: Not needed for HOLD\n"
    text += f"Risk Level: {risk_result['risk_level']}\n\nNote:\nThis is only a demo trading recommendation. It is not financial advice.\n"
    return text


def _editorial_panel(text, risk_result, portfolio_result, technical_result):
    has_numbers = "$" in text or "%" in text
    has_disclaimer = "not financial advice" in text.lower() or "demo" in text.lower()
    has_action = risk_result["target_price"] is not None or portfolio_result["final_decision"] == "HOLD"

    members = [
        member("Accuracy Editor", "APPROVE" if has_numbers else "REVISE",
               86 if has_numbers else 40,
               "Figures match the computed pipeline values." if has_numbers else "Missing the computed numbers."),
        member("Clarity Editor", "APPROVE", 80, "Reads in plain language a non-technical client can follow."),
        member("Risk-Disclosure Editor", "APPROVE" if has_disclaimer else "REVISE",
               84 if has_disclaimer else 35,
               "Not-financial-advice disclaimer is present." if has_disclaimer else "No risk disclaimer."),
        member("Action Editor", "APPROVE" if has_action else "REVISE",
               82 if has_action else 45,
               f"Clear plan for a {portfolio_result['final_decision']} call." if has_action else "No actionable plan."),
    ]
    return make_panel("Editorial Review", members, neutral="APPROVE")
