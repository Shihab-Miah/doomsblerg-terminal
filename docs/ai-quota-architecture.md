# 🧠 DoomsBlerg Quota-Proof AI Council Architecture
### How to Run an 8-Agent Buy/Sell Prediction Board Without Hitting Free API Limits

> [!IMPORTANT]
> **The Core Problem:** Free LLM APIs (Gemini, Groq) have strict **requests-per-minute (RPM)** and **daily token (TPD)** caps. If you feed 100 stocks × 200-page SEC filings into an 8-agent LLM loop every hour, you will hit `429 Quota Exhausted` within minutes.
>
> **The Solution:** **Never use LLMs to screen, calculate, or crunch numbers.** Code filters 5,000 stocks down to the top 5–10 candidates for **$0 token cost**, and a **Smart Multi-Provider LLM Router** splits the final reasoning across **separate model buckets + separate providers + local models**.

---

## 1. The 3-Stage Funnel (Reduces AI Token Usage by 98%)

```
[ 5,000+ Stocks, Crypto, Commodities, Ships, Fires ]
                        │
                        ▼  (STAGE 1: 100% Pure Python — 0 AI Tokens)
     • Screening & Technicals: RSI, MACD, volume spikes, earnings beats
     • Fundamental Math: DCF fair value gap, Altman Z-Score, F-Score
     • Geospatial Triggers: Tanker queues, crop fires, Taiwan quakes
     • Insider / Congress Filter: Recent SEC Form 4 cluster buys
                        │
                        ▼  (Narrows 5,000 → Top 5–10 Actionable Candidates)
     (STAGE 2: Local Embeddings + Compact Fact Sheet — 0 Cloud LLM Tokens)
     • ChromaDB / sentence-transformers retrieves ONLY the 3 risky paragraphs
       from a 200-page 10-K filing (not the whole PDF!)
     • Summarizes all financial tables into a tiny ~600-token JSON "Dossier"
                        │
                        ▼  (STAGE 3: Quota-Proof Multi-LLM Council)
     • Only the 5–10 winning candidates go to the AI Agent Council
     • Each agent runs on a DIFFERENT free quota bucket!
```

**Result:** Instead of burning 500,000 tokens per scan, a full market-wide Buy/Sell briefing uses **< 8,000 tokens total** — meaning you can run **50–100+ full multi-agent analyses per day for $0**.

---

## 2. Splitting Agents Across Separate Quota Buckets

Free API limits are enforced **per model family and per provider**. By routing different agents to **different models and providers**, quotas multiply instead of colliding:

| Agent Role | Primary Provider & Model | Quota Bucket | Fallback / Overflow |
| :--- | :--- | :--- | :--- |
| **1. Fundamental Auditor** | Gemini (`gemini-2.5-flash` or `gemini-3.5-flash`) | Google AI Studio Flash bucket | `gemini-2.5-flash-lite` |
| **2. Technical Quant** | **Pure Python (`pandas-ta`)** + Groq (`openai/gpt-oss-20b`) | **0 tokens** for math; Groq 20B bucket for summary | `qwen/qwen3.8-27b` |
| **3. Macro Economist** | Gemini (`gemini-2.5-flash-lite`) | Google Lite bucket (separate RPD/RPM) | Groq (`openai/gpt-oss-120b`) |
| **4. Sentiment Scout** | Groq (`qwen/qwen3.8-27b`) | Groq Qwen bucket (ultra-fast headline batching) | Local FinBERT / VADER (**0 API calls**) |
| **5. Geospatial Scout** | **Pure Python Spatial Join** + Gemini (`gemma-4-31b-it`) | **0 tokens** for geo match; Gemma bucket for brief | Groq (`allam-2-7b` / `gpt-oss-20b`) |
| **6. Bull Case Advocate** | Groq (`openai/gpt-oss-120b`) | Groq 120B bucket | Gemini (`gemini-3.8-flash`) |
| **7. Bear Case Advocate** | Gemini (`gemma-4-31b-it`) | **Gemma open-weights bucket** (separate from Gemini Flash!) | Groq (`qwen/qwen3.8-27b`) |
| **8. Risk Officer (Judge)** | Gemini (`gemini-3.8-flash` or `gemini-2.5-flash`) | Google flagship Flash bucket (reads 1 compact summary) | Groq (`openai/gpt-oss-120b`) |

> [!TIP]
> **Notice two massive free-quota tricks already live on your keys:**
> 1. **Google AI Studio gives separate per-model rate limits** for `gemini-3.8-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, AND `gemma-4-31b-it` (Gemma open-weights).
> 2. **Groq gives completely separate daily quotas** for `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, and `openai/gpt-oss-20b` — and does **300–800 tokens/sec** inference!

---

## 3. Adding Zero-Limit Local AI & Optional Free Additions

To guarantee the board **never stops even if every cloud key hits a daily cap**:

1. **Local Deterministic + ML Models (0 API Tokens, Runs Offline):**
   * **Sentiment Scoring:** Use Python `ProsusAI/finbert` (tiny 400MB financial NLP model) or `VADER` for news scoring — runs 1,000 headlines/minute locally with **zero API quota**.
   * **Quantitative Ranking Engine:** Rank every stock 0–100 purely with code (DCF discount %, earnings beat streak, insider buying ratio, RSI, momentum, EIA/USDA/satellite delta) BEFORE any LLM speaks.
2. **Local Ollama Fallback (When Running on Your Laptop):**
   * Run `deepseek-r1:7b` or `qwen2.5:7b` locally on laptop CPU/GPU via Ollama (`http://localhost:11434`) — **infinite tokens, $0 forever**.
3. **Optional Free Cloud Backups (If You Want Even More Headroom):**
   * **Mistral AI (`console.mistral.ai`):** Free developer tier with separate daily tokens (`mistral-small` / `mistral-large` prototyping).
   * **OpenRouter (`openrouter.ai`):** 25+ `:free` models (50 requests/day free, or 1,000/day if you ever add a one-time $10 balance).

---

## 4. Exact Buy / Sell Decision Pipeline

```
1. CRON / TRIGGER (Every 15 min during market hours)
   └─► Pure Python scans Alpaca + Finnhub + SEC Form 4 + EIA + NASA FIRMS
   └─► Computes Quant Score (0–100) for watchlist & alerts
   └─► Drops 99% of noise (uses 0 LLM tokens)

2. SHORTLIST (Only stocks where Quant Score > 75 OR Geo/Insider alert fired)
   └─► Packs metrics, DCF gap, insider net $, and top 5 headlines into a 600-token JSON

3. PARALLEL AGENT COUNCIL (Uses 4 separate model buckets simultaneously)
   ├─► Bull Agent (Groq gpt-oss-120b) ──► 150-word Buy Thesis
   ├─► Bear Agent (Google gemma-4-31b-it) ──► 150-word Short/Risk Thesis
   └─► Sentiment + Macro (Groq qwen3.8-27b) ──► 100-word Catalyst Timing

4. RISK OFFICER VERDICT (Gemini 3.8 Flash / 2.5 Flash)
   └─► Combines Quant Math + Bull/Bear debate + Portfolio VaR check
   └─► Outputs JSON: Action (STRONG BUY / BUY / HOLD / SELL), Entry, Stop-Loss, Target, Confidence %
```

**Token Budget per Full Stock Analysis:**
* Input + Output across ALL agents combined: **~2,500 tokens total** (not 100,000!).
* With Gemini + Gemma + Groq combined, you can run **100+ full Buy/Sell committee decisions every single day** at **$0/month**, with automatic failover if any single model returns HTTP `429`.
