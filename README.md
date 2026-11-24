# 💀 DoomsBlerg Terminal

> **Bloomberg Terminal power. Zero gatekeeping. No $30,000/year bill.**

DoomsBlerg is an open-source AI-powered financial terminal that gives you the same quality of market intelligence as a Bloomberg Terminal — built with free and low-cost public data sources, multi-agent AI analysts, and a live geospatial "God's Eye" globe view.

---

## What Makes DoomsBlerg Different

| Bloomberg Terminal | DoomsBlerg Terminal |
|---|---|
| $2,500/month | ~$70/month |
| Cryptic codes like `FA`, `DES`, `YCRV` | Plain English: "Show me financials", "Company overview" |
| No geospatial layer | Built-in live globe: ships, flights, satellites, fires, earthquakes |
| Static reports | AI agents debate your stocks in real time |
| Analysts read the data | AI reads every page of the annual report for you |

---

## Core Features

### 📊 Financial Intelligence
- Real-time stock prices, options chains, and earnings estimates
- Full financial statements pulled from SEC (identical to Bloomberg)
- Macroeconomic data from the Federal Reserve (FRED)
- Treasury and corporate bond yield curves
- FX rates, commodities, and futures

### 🤖 AI Agent Council
Seven specialized agents that work for you:
- **Fundamentals Analyst** — reads the financial statements and finds red flags
- **Technical Analyst** — reads the charts and momentum signals
- **Macro Economist** — tracks interest rates, inflation, and macro trends
- **Bull Agent** — builds the strongest possible case for buying
- **Bear Agent** — builds the strongest possible case for selling
- **Sentiment Agent** — reads the news and social pulse
- **Risk Officer (Judge)** — listens to the debate and gives the final verdict

### 🌍 Geospatial Intelligence (God's Eye View — Merged)
Real-world physical signals that move markets before the news catches up:
- **Ship tracker** — live cargo ships, oil tankers, container vessels (AISStream)
- **Flight tracker** — live commercial and private aircraft (ADS-B / OpenSky)
- **Satellite tracker** — orbital paths and passes (CelesTrak)
- **Wildfire map** — active fires near oil fields, farmland, pipelines (NASA FIRMS)
- **Earthquake watch** — seismic events near infrastructure (USGS)
- **Port congestion** — supply chain bottlenecks and wait times
- **Executive jet tracker** — M&A signal from corporate fleet movements

### 💬 Plain English Commands
No memorizing codes. Just type what you want:
- `"Show me Apple's financials"` → full income statement, balance sheet, cash flow
- `"Debate this stock: Tesla"` → AI bull vs bear debate with verdict
- `"What ships are near the Strait of Hormuz"` → live maritime map
- `"What's the yield curve doing"` → current Treasury curve with context
- `"Watch the world"` → open the live 3D globe

---

## Tech Stack

```
Backend:     Python 3.12 + FastAPI
Data:        OpenBB Platform, Polygon.io, SEC EDGAR, FRED, FMP
Compute:     QuantLib, NumPy, pandas-ta, PyPortfolioOpt
AI Agents:   LangGraph, LangChain, Gemini API
Filing RAG:  LlamaIndex + ChromaDB
Geospatial:  CesiumJS, AISStream, OpenSky, NASA FIRMS, USGS, CelesTrak
Frontend:    Next.js 15 + TradingView Lightweight Charts
Real-time:   WebSocket (FastAPI + Polygon + AISStream)
Trading:     Alpaca API (paper + live)
Storage:     DuckDB + Redis + SQLite
```

---

## Project Structure

```
doomsblerg-terminal/
├── backend/
│   ├── data_engine/      # All data fetching and normalization
│   ├── compute_engine/   # All math and quant models (no LLMs here)
│   ├── agents/           # AI agent definitions and tools
│   └── api/              # FastAPI routes and WebSocket handlers
├── frontend/
│   └── src/              # Next.js terminal UI
├── geospatial/           # God's Eye View integration layer
└── docs/                 # Documentation
```

---

## Build Phases

| Phase | What Gets Built |
|---|---|
| Phase 1 | Data Engine — all data sources connected and normalized |
| Phase 2 | Compute Engine — all math models (DCF, bonds, Greeks, VaR) |
| Phase 3 | AI Agent Layer — the 7-agent council with LangGraph |
| Phase 4 | Plain English command system (all Bloomberg equivalents + originals) |
| Phase 5 | Geospatial Intelligence layer (God's Eye View merged in) |
| Phase 6 | Terminal UI — multi-panel workstation with live globe |
| Phase 7 | Backtesting + paper trading via Alpaca |

---

## Cost Breakdown

| Service | Cost |
|---|---|
| Polygon.io real-time (stocks + options) | $29/mo |
| Financial Modeling Prep (earnings, estimates) | $15/mo |
| AISStream ship tracking | Free |
| OpenSky Network flight tracking | Free |
| NASA FIRMS, USGS, FRED, SEC EDGAR | Free |
| AI agent API calls (Gemini) | ~$5–15/mo |
| **Total** | **~$55–65/month** |

Bloomberg Terminal: $2,000–$2,500/month. DoomsBlerg: $55–65/month.

---

## Status

🚧 **Phase 1 — Data Engine: In Progress**

---

## License

MIT — Free for everyone. No gatekeeping.
