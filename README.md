# 💀 DoomsBlerg Terminal

> **Bloomberg Terminal power. Zero gatekeeping. No $30,000/year bill.**

DoomsBlerg is an open-source AI-powered financial terminal that gives you the same quality of market intelligence as a Bloomberg Terminal — built with **$0/month** public data sources, a cloud-only multi-agent AI council (optimized for low-end laptops), and a live geospatial "God's Eye" globe view.

---

## What Makes DoomsBlerg Different

| Bloomberg Terminal | DoomsBlerg Terminal |
|---|---|
| $2,500/month | **$0/month** |
| Cryptic codes like `FA`, `DES`, `YCRV` | Plain English: "Show me financials", "Company overview" |
| No geospatial layer | Built-in live globe: ships, flights, satellites, fires, earthquakes |
| Static reports | 8 cloud AI agents debate your stocks in real time |
| Analysts read the data | AI reads key filing sections & generates Buy/Sell verdicts |

---

## Core Features

### 📊 Financial Intelligence
- Real-time stock prices, options chains, and earnings estimates
- Full financial statements pulled from SEC (identical to Bloomberg)
- Macroeconomic data from the Federal Reserve (FRED)
- Treasury and corporate bond yield curves
- FX rates, commodities, energy (EIA), crops (USDA), and weather (NOAA/Open-Meteo)

### 🤖 AI Agent Council (100% Cloud Auto-Switcher)
Eight specialized agents rotating across Google Gemini/Gemma, Groq, OpenRouter, and Kilo AI Gateway:
- **Fundamentals Analyst** — audits 10-K/10-Q filings and flags accounting risks
- **Technical Quant** — computes momentum, RSI, MACD, and options Greeks in pure Python
- **Macro Economist** — tracks interest rates, inflation, and yield curves
- **Bull Agent** — builds the strongest possible case for buying
- **Bear Agent** — builds the strongest possible case for selling
- **Sentiment Scout** — reads news mood with lightweight VADER + cloud LLMs
- **Geospatial Scout** — correlates ships, flights, wildfires, and quakes to market shocks
- **Risk Officer (Judge)** — weighs every input and delivers the Buy/Sell verdict & confidence %

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

## Tech Stack (Low-End Laptop Friendly — 100% Cloud AI, $0/Month)

```
Backend:     Python 3.12 + FastAPI (< 250 MB total RAM, zero local LLMs)
Data:        Alpaca, Finnhub, FRED, SEC EDGAR, EIA, USDA NASS, NOAA, FMP, Tiingo, Twelve Data, Massive
Compute:     NumPy, SciPy, pandas-ta, VADER (pure Python math — zero LLM arithmetic)
AI Router:   Auto-switching Multi-Cloud Council (Google Gemini + Groq + OpenRouter + Kilo Gateway)
Geospatial:  CesiumJS, AISStream, OpenSky, adsb.lol, NASA FIRMS, USGS, CelesTrak, Open-Meteo
Frontend:    Next.js 15 + TradingView Lightweight Charts
Trading:     Alpaca Markets Paper & Live API
Storage:     DuckDB + SQLite (FTS5 search) — embedded, zero cloud DB cost
```

---

## Project Structure

```
doomsblerg-terminal/
├── backend/
│   ├── data_engine/      # All data fetching and normalization
│   ├── compute_engine/   # All math and quant models (no LLMs here)
│   ├── agents/           # 8-agent council + multi-cloud failover router
│   └── api/              # FastAPI routes and WebSocket handlers
├── frontend/
│   └── src/              # Next.js terminal UI
├── geospatial/           # God's Eye View integration layer
└── docs/                 # Documentation & Plain English dictionary
```

---

## Build Phases

| Phase | What Gets Built |
|---|---|
| Phase 1 | Data Engine — all 17 keys + keyless feeds normalized into one router |
| Phase 2 | Compute Engine — all math models (DCF, Greeks, Z-Score, technicals, VADER) |
| Phase 3 | Multi-Cloud AI Router + 8-Agent Council (Gemini + Groq + OpenRouter + Kilo) |
| Phase 4 | Plain English command system (all Bloomberg equivalents + originals) |
| Phase 5 | Geospatial Intelligence layer (God's Eye View merged in) |
| Phase 6 | Terminal UI — lightweight multi-panel workstation with live globe |
| Phase 7 | Backtesting + paper trading via Alpaca |

---

## Cost Breakdown

| Service | Cost |
|---|---|
| Financial & Macro Data (FRED, SEC, Alpaca, Finnhub, FMP, Tiingo, Twelve Data, Massive, Alpha Vantage) | **$0** |
| Energy, Crops & Weather (EIA, USDA NASS, NOAA CDO, Open-Meteo, NASA POWER) | **$0** |
| Geospatial Feeds (AISStream, OpenSky, adsb.lol, NASA FIRMS, USGS, CelesTrak) | **$0** |
| Multi-Cloud AI Agents (Gemini, Groq, OpenRouter, Kilo Gateway) | **$0** |
| Paper Trading & Execution (Alpaca) | **$0** |
| **Total** | **$0 / month** |

Bloomberg Terminal: $2,000–$2,500/month. DoomsBlerg: **$0/month**.

---

## Status

✅ **Phase 1 — Unified Data Engine: Complete & Live Verified (20/20 checks passing)**
🚧 **Phase 2 — Pure Compute Engine: Next**

---

## License

MIT — Free for everyone. No gatekeeping.
