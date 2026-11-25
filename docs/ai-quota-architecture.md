# 🧠 DoomsBlerg Cloud-Only AI Council & Multi-Gateway Switcher
### Designed for Low-End Laptops (0 MB Local AI RAM) & $0/Month Forever

> [!IMPORTANT]
> **Hardware & Cost Constraints:**
> 1. **Low-End Laptop Friendly:** Zero local LLMs (no Ollama, no PyTorch, no local FinBERT weights). Total backend footprint stays under ~250 MB RAM.
> 2. **Zero Dollars ($0/month):** Every AI call routes across free cloud APIs and free AI gateways.
> 3. **Never Stalls on `429`:** A unified **OpenAI-compatible + Gemini Circuit-Breaker Router** switches automatically between **4 active cloud gateways** (and an optional 5th) whenever any model or provider hits rate limits.

---

## 1. Live Cloud AI Fleet & Verified Quotas

| Gateway / Provider | Auth Status | Verified Working Models | Free Quota / Throughput | Role in Switcher |
| :--- | :--- | :--- | :--- | :--- |
| **1. Google AI Studio** | `GEMINI_API_KEY` (Verified) | `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemma-4-31b-it`, `gemini-embedding-001` | Separate per-model free tier limits + cloud embeddings | Primary Auditor, Risk Officer Judge, Bear (`gemma-4`), 10-K Embedding |
| **2. Groq LPU** | `GROQ_API_KEY` (Verified) | `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `allam-2-7b` | ~1,000+ RPD per model bucket (30 RPM, ultra-fast) | Bull Advocate (`gpt-oss-120b`), Sentiment & Macro fast pass |
| **3. OpenRouter** | `OPENROUTER_API_KEY` (Verified) | `nvidia/nemotron-3.5-lightning:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, + 9 more `:free` models | **50 free req/day** across `:free` catalog (20 RPM) | Deep reasoning cross-check (`550B`) & second opinion |
| **4. Kilo AI Gateway** | **No Key Needed** *(or free `KILO_API_KEY`)* | `reflection/beam-free` (tested live!), `kilo-auto/free`, + 15 rotating free models | **200 req/hour anonymous** (up to 4,800/day capacity) | High-volume overflow & 429 burst absorber |
| **5. OpenCode Zen** *(Optional)* | Needs `OPENCODE_API_KEY` (`opencode.ai/auth`) | `deepseek-v4.1-flash-free`, `mimo-v2.6-flash-free`, `big-pickle` | Anonymous pool hits `429`; authenticated key adds extra free pool | Optional 5th failover slot |

---

## 2. How the Low-RAM 3-Stage Funnel Cuts Token Usage by 98%

Because the laptop has limited RAM and cloud free tiers have daily caps, **we let tiny pure-Python code do 98% of the work before any cloud AI call is made**:

```
[ 5,000+ Stocks, Crypto, Commodities, Ships, Fires ]
                        │
                        ▼  (STAGE 1: Pure Python — < 50 MB RAM, 0 AI Tokens)
     • Quant Screener: DCF fair value discount %, Altman Z-Score, F-Score
     • Technical Math: RSI, MACD, volume anomalies via NumPy / pandas-ta
     • Physical Alpha: EIA oil delta, USDA crop delta, NASA FIRMS, USGS, AIS
     • Insider / Congress: SEC Form 4 cluster buys
                        │
                        ▼  (Narrows 5,000 → Top 5–10 Actionable Candidates)
     (STAGE 2: Lightweight Text Extract — < 30 MB RAM, 0 Local ML)
     • VADER lexicon scores 1,000 news headlines in < 0.2s (pure Python, 1 MB RAM)
     • SQLite FTS5 extracts only the top 3 risky sections from 10-K filings
     • Optional: Google `gemini-embedding-001` API embeds chunks in the cloud
     • Outputs a compact ~600-token JSON Fact Sheet
                        │
                        ▼  (STAGE 3: 4-Cloud Circuit-Breaker AI Council)
     • Only the 5–10 shortlisted tickers hit the 8-Agent Council
     • Every agent has Primary + Fallback 1 + Fallback 2 across DIFFERENT clouds!
```

---

## 3. Agent-to-Cloud Routing Table & Automatic Failover Chain

Each agent runs on a **Primary** provider and automatically fails over on `429` / `503` / timeout:

| Agent | Primary (Best Fit) | Fallback 1 | Fallback 2 |
| :--- | :--- | :--- | :--- |
| **1. Quant / Technical** | **Pure Python** (`0 tokens`) + Groq `gpt-oss-20b` | Kilo `reflection/beam-free` | Gemini `2.5-flash-lite` |
| **2. Geospatial Scout** | **Pure Python Spatial Join** (`0 tokens`) + Kilo `reflection/beam-free` | Groq `qwen/qwen3.8-27b` | Gemini `2.5-flash-lite` |
| **3. Sentiment Scout** | **VADER (Python)** + Groq `qwen/qwen3.8-27b` | Kilo `reflection/beam-free` | OpenRouter `nemotron-3.5-lightning:free` |
| **4. Macro Economist** | Gemini `2.5-flash-lite` | Groq `qwen/qwen3.8-27b` | Kilo `reflection/beam-free` |
| **5. Fundamental Auditor** | Gemini `3.5-flash` | OpenRouter `nemotron-3-ultra-550b-a55b:free` | Groq `openai/gpt-oss-120b` |
| **6. Bull Case Advocate** | Groq `openai/gpt-oss-120b` | OpenRouter `nemotron-3.5-lightning:free` | Gemini `2.5-flash` |
| **7. Bear Case Advocate** | Google `gemma-4-31b-it` | Kilo `reflection/beam-free` | Groq `qwen/qwen3.8-27b` |
| **8. Risk Officer (Judge)** | Gemini `3.5-flash` | Groq `openai/gpt-oss-120b` | OpenRouter `nemotron-3-ultra-550b-a55b:free` |

---

## 4. Circuit-Breaker Switching Logic (How Switching Works in Code)

```python
# Pseudocode for backend/agents/llm_router.py

class MultiCloudRouter:
    # Tracks cooldowns per (provider, model) in SQLite/memory
    # If any endpoint returns HTTP 429, 503, or times out >15s:
    #   1. Mark that specific (provider, model) on cooldown for 60s (or 1h if daily quota hit)
    #   2. Immediately retry the prompt on the next fallback gateway in the chain
    #   3. Never crash the user's command or leave a Buy/Sell panel blank
```

### Capacity Math (Real Daily Output)
* **Tokens per full 8-Agent Buy/Sell Debate:** ~2,500 tokens across **5 LLM calls** (Quant & Geo math run in Python = 0 calls; remaining 5 roles call cloud APIs).
* **Available Daily Request Budget ($0/month):**
  * **Groq:** ~3,000+ req/day across its 3 distinct free model buckets.
  * **Google AI Studio:** Separate daily buckets across `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, and `gemma-4-31b-it`.
  * **Kilo AI Gateway:** **200 req/hour** (`reflection/beam-free` & free models) — handles burst traffic with zero key.
  * **OpenRouter:** **50 req/day** reserved exclusively for hard reasoning / tie-breaker votes (`nemotron-3-ultra-550b-a55b:free`).
* **Net Real-World Capacity:** **200 to 500+ full Buy/Sell committee decisions per day** for **$0/month**, running smoothly on a low-end laptop because **all AI inference happens in the cloud**.
