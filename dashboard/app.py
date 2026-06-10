import sys
import os
import time
import math

import pandas as pd
import altair as alt
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from config import MARKETS, CACHE_TTL_SECONDS, openai_enabled, use_mcp
from pipeline import run_pipeline, AGENTS
from agents.market_data_agent import get_market_data

BG = "#0a0a0a"; PANEL = "#141414"; BORDER = "#262626"; TEXT = "#e8e8e8"
MUTED = "#8a8a8a"; LIME = "#C6F432"; RED = "#ff5c5c"; AMBER = "#e0a93b"

st.set_page_config(page_title="AI Trading Desk", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    .stApp { background: #0a0a0a; color: #e8e8e8; }
    section[data-testid="stSidebar"] { background: #0d0d0d; border-right: 1px solid #262626; }
    /* keep the header (and its sidebar toggle) usable — just make it blend in */
    #MainMenu, footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    html, body, [class*="css"], p, label, span, div { font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3, h4 { font-family: 'Space Grotesk', 'Inter', sans-serif; color: #f4f4f4; font-weight: 600; }
    .muted { color: #8a8a8a; font-size: 0.85rem; }

    .stButton>button { background: #C6F432; color: #0a0a0a; border: none; border-radius: 8px;
        padding: 11px 20px; font-weight: 700; width: 100%; font-family: 'Space Grotesk', sans-serif; cursor: pointer;
        transition: filter 0.18s ease; }
    .stButton>button:hover { filter: brightness(1.08); }
    .stButton>button:focus-visible { outline: 2px solid #C6F432; outline-offset: 2px; }

    [data-testid="stMetric"] { background: #141414; border: 1px solid #262626; border-radius: 10px; padding: 14px 16px; }
    [data-testid="stMetricValue"] { color: #f4f4f4 !important; font-family: 'IBM Plex Mono', monospace; font-size: 1.4rem; }
    [data-testid="stMetricLabel"] { color: #8a8a8a !important; text-transform: uppercase; font-size: 0.66rem; letter-spacing: 0.6px; }

    .brand { display: flex; align-items: center; gap: 12px; }
    .brand h1 { margin: 0; font-size: 1.85rem; letter-spacing: -0.5px; }
    .brand .tag { font-family: 'IBM Plex Mono', monospace; color: #C6F432; font-size: 0.7rem;
        border: 1px solid #2f3a17; background: #11160a; padding: 3px 9px; border-radius: 999px; }
    .sec { font-family: 'IBM Plex Mono', monospace; color: #8a8a8a; font-size: 0.72rem;
        text-transform: uppercase; letter-spacing: 1.4px; margin: 16px 0 8px; }

    .pipeline { display: flex; gap: 8px; flex-wrap: wrap; }
    .step { flex: 1 1 150px; background: #141414; border: 1px solid #262626; border-radius: 10px;
        padding: 11px 13px; display: flex; align-items: center; gap: 10px; min-width: 145px; }
    .step .num { font-family: 'IBM Plex Mono', monospace; font-size: 0.64rem; color: #8a8a8a; }
    .step .name { font-size: 0.8rem; font-weight: 600; line-height: 1.2; }
    .step .dot { width: 9px; height: 9px; border-radius: 50%; background: #2c2c2c; flex-shrink: 0; }
    .step.running { border-color: #C6F432; } .step.running .dot { background: #C6F432; animation: pulse 0.9s infinite ease-in-out; }
    .step.running .name { color: #C6F432; } .step.done { border-color: #2f3a17; } .step.done .dot { background: #C6F432; }
    .step .chk { width: 13px; height: 13px; flex-shrink: 0; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }
    @media (prefers-reduced-motion: reduce) { .step.running .dot { animation: none; } }

    .mcp { background: #141414; border: 1px solid #262626; border-radius: 10px; padding: 12px 14px; }
    .mcp-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }
    .mcp-row .sdot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .mcp-row .srv { color: #8a8a8a; } .mcp-row .ms { margin-left: auto; color: #8a8a8a; }

    .hero { background: #141414; border: 1px solid #262626; border-radius: 14px; padding: 22px 24px; height: 100%; }
    .badge { display: inline-block; padding: 9px 26px; border-radius: 10px; font-family: 'Space Grotesk', sans-serif;
        font-size: 1.8rem; font-weight: 700; letter-spacing: 1px; }
    .badge.BUY { background: #C6F432; color: #0a0a0a; } .badge.SELL { background: #ff5c5c; color: #fff; }
    .badge.HOLD { background: #e0a93b; color: #0a0a0a; }
    .stat { background: #141414; border: 1px solid #262626; border-radius: 10px; padding: 15px; }
    .stat .lbl { color: #8a8a8a; font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.6px; }
    .stat .val { font-family: 'IBM Plex Mono', monospace; font-size: 1.25rem; font-weight: 600; margin-top: 4px; }

    .fng-track { background: linear-gradient(90deg,#ff5c5c,#e0a93b,#C6F432); height: 8px; border-radius: 6px; position: relative; }
    .fng-mark { position: absolute; top: -4px; width: 3px; height: 16px; background: #f4f4f4; border-radius: 2px; }

    /* Debate panel */
    .dsum { color: #b9b9b9; font-style: italic; font-size: 0.86rem; margin: 2px 0 12px; }
    .members { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .member { background: #111; border: 1px solid #262626; border-radius: 10px; padding: 12px 13px; }
    .member .top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .member .mname { font-weight: 600; font-size: 0.82rem; }
    .vchip { padding: 2px 9px; border-radius: 6px; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; font-weight: 700; }
    .member .rat { color: #9a9a9a; font-size: 0.78rem; margin-top: 7px; line-height: 1.4; }
    .cbar { background: #1f1f1f; height: 5px; border-radius: 4px; margin-top: 9px; overflow: hidden; }
    .cbar > div { height: 100%; border-radius: 4px; }
    .verdict-chip { padding: 3px 12px; border-radius: 7px; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 0.8rem; }
    @media (max-width: 800px){ .members { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)

CHECK_SVG = ('<svg class="chk" viewBox="0 0 24 24" fill="none" stroke="#C6F432" stroke-width="3" '
             'stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>')
SPARK_SVG = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="#C6F432">'
             '<path d="M12 0 L14.5 9.5 L24 12 L14.5 14.5 L12 24 L9.5 14.5 L0 12 L9.5 9.5 Z"/></svg>')


def stance_color(stance: str) -> str:
    s = stance.upper()
    if s in ("BUY", "POSITIVE", "GOOD", "LOW", "APPROVE"):
        return LIME
    if s in ("SELL", "NEGATIVE", "HIGH", "STALE", "REVISE"):
        return RED
    return AMBER  # HOLD, NEUTRAL, MEDIUM, DEGRADED


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_market_data(asset_id: str, market: str, mock_flag: bool):
    config.set_mock_mode(mock_flag)
    return get_market_data(asset_id, market)


def render_pipeline(placeholder, states):
    chips = []
    for i, (key, label) in enumerate(AGENTS):
        cls = states[i]
        icon = CHECK_SVG if cls == "done" else '<span class="dot"></span>'
        chips.append(f'<div class="step {cls}">{icon}<div><div class="num">AGENT {i+1}</div>'
                     f'<div class="name">{label}</div></div></div>')
    placeholder.markdown(f'<div class="pipeline">{"".join(chips)}</div>', unsafe_allow_html=True)


def confidence_gauge(pct: int, color: str) -> str:
    r = 70; circ = math.pi * r; frac = max(0, min(100, pct)) / 100
    track = '<path d="M10 80 A70 70 0 0 1 150 80" fill="none" stroke="#1f1f1f" stroke-width="13" stroke-linecap="round"/>'
    val = (f'<path d="M10 80 A70 70 0 0 1 150 80" fill="none" stroke="{color}" stroke-width="13" '
           f'stroke-linecap="round" stroke-dasharray="{circ}" stroke-dashoffset="{circ*(1-frac):.1f}"/>')
    return (f'<svg width="160" height="96" viewBox="0 0 160 96">{track}{val}'
            f'<text x="80" y="74" text-anchor="middle" fill="#f4f4f4" font-family="IBM Plex Mono, monospace" '
            f'font-size="30" font-weight="600">{pct}%</text></svg>')


def mcp_panel(log) -> str:
    if not log:
        return '<div class="mcp"><div class="muted">No MCP calls (cache or MCP disabled).</div></div>'
    rows = []
    for c in log:
        ok = c["status"] == "ok"; col = LIME if ok else RED
        rows.append(f'<div class="mcp-row"><span class="sdot" style="background:{col}"></span>'
                    f'<span class="srv">{c["server"]}</span><span>· {c["tool"]}()</span>'
                    f'<span class="ms">{"OK" if ok else "FAIL"} · {c["ms"]}ms</span></div>')
    return f'<div class="mcp">{"".join(rows)}</div>'


def render_panel(panel: dict) -> str:
    vcol = stance_color(panel["verdict"])
    tally = " · ".join(f"{k} {v}" for k, v in panel["tally"].items())
    head = (f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
            f'<span class="verdict-chip" style="background:{vcol};color:#0a0a0a;">{panel["verdict"]} · {panel["verdict_confidence"]}%</span>'
            f'<span class="muted">{tally}</span></div>')
    summary = f'<div class="dsum">{panel["debate_summary"]}</div>' if panel.get("debate_summary") else ""
    cards = []
    for m in panel["members"]:
        col = stance_color(m["stance"])
        cards.append(
            f'<div class="member"><div class="top"><span class="mname">{m["name"]}</span>'
            f'<span class="vchip" style="background:{col};color:#0a0a0a;">{m["stance"]}</span></div>'
            f'<div class="cbar"><div style="width:{m["confidence"]}%;background:{col};"></div></div>'
            f'<div class="rat">{m["rationale"]} <span style="color:#6f6f6f">({m["confidence"]}%)</span></div></div>')
    return head + summary + f'<div class="members">{"".join(cards)}</div>'


def price_chart(history, risk, decision):
    df = history.copy(); df["time"] = pd.to_datetime(df["timestamp"], unit="ms")
    lc = LIME if decision == "BUY" else (RED if decision == "SELL" else AMBER)
    area = alt.Chart(df).mark_area(opacity=0.10, color=lc).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(grid=False, labelColor=MUTED, tickColor=BORDER, domainColor=BORDER)),
        y=alt.Y("close:Q", title=None, scale=alt.Scale(zero=False)))
    line = alt.Chart(df).mark_line(color=lc, strokeWidth=1.8).encode(
        x="time:T", y=alt.Y("close:Q", scale=alt.Scale(zero=False),
        axis=alt.Axis(grid=True, gridColor="#1c1c1c", labelColor=MUTED, tickColor=BORDER, domainColor=BORDER)),
        tooltip=[alt.Tooltip("time:T", title="Time"), alt.Tooltip("close:Q", title="Price", format="$,.2f")])
    layers = [area, line]
    for label, value, color in [("Entry", risk.get("entry_price"), TEXT), ("Target", risk.get("target_price"), LIME),
                                ("Stop", risk.get("stop_loss"), RED)]:
        if value is None:
            continue
        rdf = pd.DataFrame({"y": [value], "label": [f"{label} ${value:,.0f}"]})
        layers.append(alt.Chart(rdf).mark_rule(color=color, strokeDash=[5, 4], strokeWidth=1.3).encode(y="y:Q"))
        layers.append(alt.Chart(rdf).mark_text(color=color, align="left", dx=6, dy=-6, fontSize=11).encode(
            y="y:Q", text="label:N", x=alt.value(8)))
    chart = alt.layer(*layers).properties(height=330).configure_view(fill=PANEL, stroke=BORDER).configure(background=PANEL)
    st.altair_chart(chart, width="stretch")


def _tech_extra(tech):
    ind = tech.get("indicators")
    if ind:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("RSI(14)", ind["rsi"]); m2.metric("MACD hist", ind["macd_hist"])
        m3.metric("10/30 MA", f"{ind['ma_fast']:,.0f}/{ind['ma_slow']:,.0f}"); m4.metric("ROC(10)", f"{ind['roc']}%")


def _sent_extra(sent):
    fng = sent.get("fear_greed")
    if fng:
        st.markdown(
            f'<p class="muted" style="margin:4px 0;">Fear &amp; Greed: <b style="color:#e8e8e8">{fng["value"]}/100 · '
            f'{fng["classification"]}</b> · news {sent["news_score"]}/100 · blended {sent["score"]}/100</p>'
            f'<div class="fng-track"><div class="fng-mark" style="left:{fng["value"]}%"></div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="muted">News {sent["news_score"]}/100 · no equity Fear &amp; Greed index.</p>', unsafe_allow_html=True)
    st.markdown('<p class="muted" style="margin-top:8px;">Headlines:</p>', unsafe_allow_html=True)
    for h in sent["headlines"][:4]:
        st.markdown(f'<p class="muted">· {h}</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div class="brand">{SPARK_SVG}<h2 style="margin:0">Trading Desk</h2></div>', unsafe_allow_html=True)
    st.markdown('<p class="muted">24 sub-agents · 6 panels · MCP-powered</p>', unsafe_allow_html=True)
    st.markdown("---")

    market_label = st.radio("Market", ["Crypto", "Stocks"], horizontal=True)
    market_key = "crypto" if market_label == "Crypto" else "stocks"
    assets = MARKETS[market_key]["assets"]
    asset = st.selectbox("Asset", list(assets), format_func=lambda a: f"{assets[a]} · {a}")

    mock_flag = st.checkbox("Mock mode (offline data)", value=config.mock_mode(),
                            help="Run fully offline. MCP tools still fire on baked-in data.")
    ai_on = openai_enabled()
    st.markdown(
        f'<p class="muted">AI reasoning: <span style="color:{LIME if ai_on else MUTED}">'
        f'{"OpenAI active" if ai_on else "rule-based fallback"}</span></p>'
        f'<p class="muted">Data layer: <span style="color:{LIME if use_mcp() else MUTED}">'
        f'{"MCP (4 servers)" if use_mcp() else "direct"}</span></p>', unsafe_allow_html=True)
    st.markdown("---")
    run = st.button("Run Agents")
    st.markdown('<p class="muted">Demo only — not financial advice.</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f'<div class="brand">{SPARK_SVG}<h1>AI Trading Desk</h1>'
            f'<span class="tag">2026 · 24 SUB-AGENTS · 4 MCP SERVERS</span></div>', unsafe_allow_html=True)
st.markdown('<p class="muted">Six agents — each a 4-member debate panel — call MCP data tools, '
            'argue, vote, and pass a verdict down the pipeline to one decision.</p>', unsafe_allow_html=True)

st.markdown('<div class="sec">Agent pipeline</div>', unsafe_allow_html=True)
pipeline_ph = st.empty()
render_pipeline(pipeline_ph, ["pending"] * 6)

if run:
    states = ["pending"] * 6

    def on_step(index, key, state):
        states[index] = state
        render_pipeline(pipeline_ph, states)
        time.sleep(0.2)

    with st.spinner("Agents analyzing, debating, and voting…"):
        md = load_market_data(asset, market_key, mock_flag)
        results = run_pipeline(asset, on_step=on_step, market_data=md, market=market_key)

    market = results["market_data"]; tech = results["technical"]; sent = results["sentiment"]
    risk = results["risk"]; port = results["portfolio"]; panels = results["panels"]

    if market.get("notice"):
        st.info(market["notice"])

    st.markdown('<div class="sec">MCP tools fired</div>', unsafe_allow_html=True)
    st.markdown(mcp_panel(results.get("mcp_log", [])), unsafe_allow_html=True)

    st.markdown('<div class="sec">Market</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Asset", market["symbol"])
    c2.metric("Price", f"${market['current_price']:,.2f}")
    c3.metric("24h", f"{market['price_change_24h']:.2f}%")
    mcap = market.get("market_cap")
    c4.metric("Market Cap", f"${mcap/1e9:,.1f}B" if mcap else "—")

    decision = port["final_decision"]; confidence = port["confidence"]
    badge_color = LIME if decision == "BUY" else (RED if decision == "SELL" else AMBER)
    st.markdown('<div class="sec">Decision</div>', unsafe_allow_html=True)
    h1, h2 = st.columns([1, 1.25])
    with h1:
        st.markdown(
            f"""<div class="hero"><div class="muted">FINAL DECISION · {port['agreement']}</div>
            <div style="margin:14px 0 6px;"><span class="badge {decision}">{decision}</span></div>
            <div style="display:flex;align-items:center;gap:14px;margin-top:8px;">{confidence_gauge(confidence, badge_color)}
            <div><div class="muted">CONFIDENCE</div><div class="muted" style="max-width:160px;margin-top:4px;">
            committee agreement &times; conviction, minus risk/data haircuts</div></div></div></div>""",
            unsafe_allow_html=True)
    with h2:
        e, t, s = risk["entry_price"], risk["target_price"], risk["stop_loss"]
        atr_txt = (f" · ATR ${risk['atr']:,.2f} ({risk['atr_pct']}%) · R:R {risk['reward_risk']}" if risk.get("atr") else "")
        st.markdown(
            f"""<div class="hero"><div style="display:flex;gap:12px;">
            <div class="stat" style="flex:1"><div class="lbl">Entry</div><div class="val">${e:,.2f}</div></div>
            <div class="stat" style="flex:1"><div class="lbl">Target</div><div class="val" style="color:{LIME}">{('$'+format(t,',.2f')) if t else '—'}</div></div>
            <div class="stat" style="flex:1"><div class="lbl">Stop-Loss</div><div class="val" style="color:{RED}">{('$'+format(s,',.2f')) if s else '—'}</div></div></div>
            <div class="muted" style="margin-top:12px;">Risk: <b style="color:#e8e8e8">{risk['risk_level']}</b> · method: {risk['method']}{atr_txt}</div></div>""",
            unsafe_allow_html=True)

    st.markdown('<div class="sec">Price · with trade levels</div>', unsafe_allow_html=True)
    if market.get("history") is not None and len(market["history"]):
        price_chart(market["history"], risk, decision)

    # ---- interactive debate panels (what each agent is doing) -----------
    st.markdown('<div class="sec">Agent debates · 24 sub-agents</div>', unsafe_allow_html=True)
    open_by_default = {"technical", "sentiment", "portfolio"}
    extras = {
        "technical": lambda: _tech_extra(tech),
        "sentiment": lambda: _sent_extra(sent),
        "portfolio": lambda: st.json({"votes": port["votes"], "combined_score": port["combined_score"],
                                      "confidence": confidence, "agreement": port["agreement"]}),
        "explanation": lambda: st.markdown(results["explanation"]),
    }
    for key, label in AGENTS:
        panel = panels.get(key)
        if not panel:
            continue
        with st.expander(f"{label}  —  {panel['title']} → {panel['verdict']}", expanded=key in open_by_default):
            st.markdown(render_panel(panel), unsafe_allow_html=True)
            if key in extras:
                extras[key]()

    st.markdown("---")
    st.markdown('<p class="muted">Demo only — not financial advice. Data via MCP: CoinGecko · CoinDesk · '
                'alternative.me · Yahoo Finance.</p>', unsafe_allow_html=True)
