# AI Trading Desk — multi-agent debate pipeline

A multi-agent trading terminal for **two markets** (crypto + stocks). Six
specialized agents — **each a 4-member debate panel (24 sub-agents total)** —
fetch data **through MCP tools**, argue, vote, and pass a verdict down the
pipeline to one BUY / SELL / HOLD decision with a **computed** confidence score.

> Demo and educational purposes only. **Not financial advice.**

---

## How it works

```
4 MCP SERVERS (stdio)        6 AGENTS, each a 4-member debate panel (24 sub-agents)
 market-data-server  ─┐   1 Market Data ──► Data Validation Council (Source·Liquidity·Freshness·Anomaly)
 stocks-server       ─┤   2 Technical  ───► Technical Desk        (RSI·MACD·Trend·Momentum)
 news-server         ─┼─► 3 Sentiment  ───► Sentiment Desk        (News·Fear&Greed·Keyword·Contrarian)
 fear-greed-server   ─┘   4 Risk       ───► Risk Committee        (ATR·Reward:Risk·Stop·Exposure)
                          5 Portfolio  ───► Investment Committee  (Bull·Bear·RiskMgr·Quant)
                          6 Explanation ──► Editorial Review      (Accuracy·Clarity·Disclosure·Action)
```

Every sub-agent's **vote and confidence are computed in plain Python** from real
signals (deterministic, offline-safe). `tally_votes` (`lib/debate.py`) turns each
panel into a verdict that flows downstream. A **single batched OpenAI call** adds
a one-line debate summary per panel — the LLM never invents or changes a number.

The agents are the **MCP client**: they open a stdio `ClientSession` to each
server, call its tools, and log every call. The dashboard shows that log live.

---

## Two markets

| Market | Assets | Data (MCP) | Sentiment |
|--------|--------|------------|-----------|
| Crypto | BTC / ETH / SOL | market-data-server (CoinGecko) | CoinDesk news + Fear & Greed |
| Stocks | AAPL / TSLA / NVDA | stocks-server (Yahoo Finance) | Yahoo per-ticker news (no equity F&G) |

The Technical, Risk, Portfolio and Explanation agents are market-agnostic — they
work off OHLC, so the same debate pipeline analyses either market.

## MCP servers (`mcp_servers/`)

| Server | Tool(s) | Source |
|--------|---------|--------|
| `market-data-server` | `get_price`, `get_ohlc_history` | CoinGecko |
| `stocks-server` | `get_quote`, `get_ohlc_history` | Yahoo Finance |
| `news-server` | `get_headlines` | CoinDesk RSS |
| `fear-greed-server` | `get_fear_greed` | alternative.me |

Each honors `MOCK_MODE`, so **MCP tools fire even fully offline**. Test directly:

```bash
python mcp_servers/stocks_server.py --test
python lib/mcp_client.py            # fire a tool on every server via the MCP client
```

---

## Analytical depth (computed in Python, never by the LLM)

- **Technical:** RSI(14), 10/30 MA crossover, MACD(12,26,9), 10-bar ROC.
- **Risk:** ATR-based stop/target (1.5×/2.5×, R:R 1.67), fixed-% fallback.
- **Sentiment:** headlines (OpenAI/keyword) blended with Fear & Greed (`0.6·news + 0.4·F&G`).
- **Confidence:** `committee_confidence × (0.5 + 0.5·agreement)`, with haircuts for
  high risk and weak upstream data trust (formula in `agents/portfolio_agent.py`).
- **AI:** OpenAI (`gpt-4o-mini` default) for sentiment, the debate summaries, and the
  final briefing. Missing `OPENAI_API_KEY` → rule-based fallback, runs fully offline.

---

## Run

```bash
python -m pip install -r requirements.txt

streamlit run dashboard/app.py            # dashboard (MCP servers auto-spawn via stdio)
python main.py bitcoin                    # CLI — crypto
python main.py AAPL --market stocks       # CLI — stocks

MOCK_MODE=1 streamlit run dashboard/app.py   # fully offline; MCP tools still fire
export OPENAI_API_KEY=sk-...                  # enable OpenAI reasoning
```

Market (Crypto/Stocks), asset, and Mock mode are sidebar controls.

---

## 10-minute demo script (mapped to the marking criteria)

1. **Technical Implementation (20%)** — Run Agents: the 6-agent pipeline lights up and
   the **"MCP tools fired"** panel lists each `server · tool · OK · ms`. MCP fires, live.
2. **Agent Design (20%)** — open the **Agent debates**: each agent is a 4-member panel
   (24 sub-agents) that votes a verdict; data access is a separate MCP tool layer.
3. **Quality of Output (20%)** — hero BUY/SELL/HOLD + **computed** confidence gauge +
   entry/target/stop + OpenAI briefing. Real RSI/MACD/MA/ATR shown per panel.
4. **Creativity & Market Choice (20%)** — switch **Crypto ↔ Stocks**; the debate panels,
   the Fear & Greed edge, and 4 MCP servers go beyond a single-market demo.
5. **Presentation (20%)** — clean lime-on-black terminal, price chart with trade levels,
   per-panel debate summaries. Tick **Mock mode** to prove it survives an outage with
   zero crashes (MCP still fires on baked data).

---

## Project structure

```
config.py                  # markets, toggles (MOCK_MODE, USE_MCP), constants
pipeline.py                # runs the 6 agents, collects 6 panels, narrates once
main.py                    # CLI entry point
agents/                    # one file per agent; each builds a 4-member debate panel
mcp_servers/               # 4 FastMCP servers (market, stocks, news, fear-greed)
lib/
  debate.py                # panel tally + single batched LLM narration
  mcp_client.py            # stdio MCP client + shared call log
  indicators.py            # pure RSI / MACD / MA / ATR math
  llm.py                   # OpenAI wrapper with graceful fallback
  mock_data.py             # baked-in offline data (crypto + stocks)
dashboard/app.py           # Streamlit trading terminal + interactive debate panels
```
