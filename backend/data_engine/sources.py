"""
DoomsBlerg Zero-Dollar Data Source Configuration
=================================================
Every single data source here is FREE.
No paid APIs. No subscriptions. No credit cards.

This file maps every data category to its free source
and explains the fallback chain if one source is unavailable.
"""

# ─────────────────────────────────────────────────────────────
# REAL-TIME STOCK PRICES
# Source 1: Alpaca (free WebSocket streaming via IEX feed)
# Source 2: Finnhub (free tier WebSocket, global markets)
# Fallback:  yfinance (delayed quotes, no key needed)
# ─────────────────────────────────────────────────────────────
ALPACA_BASE_URL     = "https://api.alpaca.markets"
ALPACA_DATA_URL     = "https://data.alpaca.markets"
ALPACA_WS_URL       = "wss://stream.data.alpaca.markets/v2/iex"
# Free account at: https://alpaca.markets (no deposit needed for paper trading + data)

FINNHUB_BASE_URL    = "https://finnhub.io/api/v1"
FINNHUB_WS_URL      = "wss://ws.finnhub.io"
# Free key at: https://finnhub.io (no credit card)

# ─────────────────────────────────────────────────────────────
# FINANCIAL STATEMENTS (Balance Sheet, Income, Cash Flow)
# Source: SEC EDGAR XBRL — the ORIGINAL source Bloomberg uses
# 100% free, no key needed
# ─────────────────────────────────────────────────────────────
SEC_EDGAR_BASE      = "https://data.sec.gov"
SEC_COMPANY_FACTS   = "https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
SEC_COMPANY_CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/{cik}/{taxonomy}/{concept}.json"
SEC_SUBMISSIONS     = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FULL_TEXT       = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom"
# No key, no signup — public government API

# ─────────────────────────────────────────────────────────────
# OPTIONS CHAIN DATA
# Source 1: yfinance (live snapshots — no key needed)
# Source 2: Tradier sandbox (free developer account)
# Greeks: Computed locally with Black-Scholes (QuantLib / scipy)
# ─────────────────────────────────────────────────────────────
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
# Free sandbox key at: https://developer.tradier.com

# ─────────────────────────────────────────────────────────────
# ANALYST EARNINGS ESTIMATES & CONSENSUS
# Source 1: Finnhub free tier (EPS estimates, analyst targets)
# Source 2: yfinance (.earnings_estimate, .analyst_price_targets)
# Fallback:  SEC EDGAR actual reported EPS (post-earnings)
# ─────────────────────────────────────────────────────────────
# Same Finnhub key from above — covers estimates too

# ─────────────────────────────────────────────────────────────
# MACROECONOMIC DATA (Inflation, GDP, Rates, Unemployment)
# Source: FRED (Federal Reserve Bank of St. Louis) — 100% free
# 800,000+ economic time series — same data Bloomberg ECO uses
# ─────────────────────────────────────────────────────────────
FRED_BASE_URL       = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
FRED_API_URL        = "https://api.stlouisfed.org/fred/series/observations"
# Free key at: https://fred.stlouisfed.org/docs/api/api_key.html (instant, no credit card)

# Common FRED series IDs (same as Bloomberg ECST)
FRED_SERIES = {
    "inflation_cpi":      "CPIAUCSL",   # CPI All Items (Bloomberg: CPI YOY)
    "core_pce":           "PCEPILFE",   # Core PCE (Fed's preferred inflation gauge)
    "fed_funds_rate":     "FEDFUNDS",   # Fed Funds Effective Rate (Bloomberg: FDTR)
    "unemployment":       "UNRATE",     # Unemployment Rate (Bloomberg: USURTOT)
    "gdp_growth":         "A191RL1Q225SBEA",  # Real GDP Growth Rate
    "10y_treasury":       "GS10",       # 10-Year Treasury Yield
    "2y_treasury":        "GS2",        # 2-Year Treasury Yield
    "3m_tbill":           "DTB3",       # 3-Month T-Bill Rate
    "sofr":               "SOFR",       # SOFR (replaces LIBOR)
    "mortgage_30y":       "MORTGAGE30US",# 30-Year Fixed Mortgage Rate
    "dollar_index":       "DTWEXBGS",  # US Dollar Trade Weighted Index
    "sp500":              "SP500",      # S&P 500 Level
    "vix":                "VIXCLS",     # VIX Volatility Index
    "consumer_sentiment": "UMCSENT",    # University of Michigan Sentiment
    "housing_starts":     "HOUST",      # Housing Starts
    "retail_sales":       "RSAFS",      # Retail Sales
    "industrial_prod":    "INDPRO",     # Industrial Production Index
    "credit_spread_hy":   "BAMLH0A0HYM2", # High Yield Credit Spread (OAS)
    "credit_spread_ig":   "BAMLC0A0CM",   # Investment Grade Credit Spread
    "m2_money_supply":    "M2SL",       # M2 Money Supply
}

# Treasury Yield Curve (direct from US Treasury — no key)
TREASURY_YIELD_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month={YYYYMM}"

# ─────────────────────────────────────────────────────────────
# FINANCIAL NEWS & HEADLINES
# Source 1: RSS feeds from primary publishers (free, unlimited)
# Source 2: Finnhub news free tier (company-specific)
# Source 3: GDELT (global macro/geopolitical events)
# ─────────────────────────────────────────────────────────────
NEWS_RSS_FEEDS = {
    "Reuters Finance":      "https://feeds.reuters.com/reuters/businessNews",
    "AP Finance":           "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "CNBC Top News":        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "MarketWatch Top":      "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Seeking Alpha":        "https://seekingalpha.com/market_currents.xml",
    "Yahoo Finance":        "https://finance.yahoo.com/news/rssindex",
    "SEC Press Releases":   "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=40&search_text=&output=atom",
    "FT Markets":           "https://www.ft.com/markets?format=rss",
    "Bloomberg Markets RSS":"https://feeds.bloomberg.com/markets/news.rss",  # Free public RSS
}

# Google News RSS (no key — unlimited requests)
GOOGLE_NEWS_FINANCE_RSS = "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"
GOOGLE_NEWS_TICKER_RSS  = "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"

# GDELT Project (global news monitoring — completely free, real-time)
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# ─────────────────────────────────────────────────────────────
# GEOSPATIAL INTELLIGENCE (All Free Government/Community Feeds)
# ─────────────────────────────────────────────────────────────

# Ships — AISStream.io (free WebSocket)
AIS_STREAM_URL   = "wss://stream.aisstream.io/v0/stream"
# Free key at: https://aisstream.io

# Flights — OpenSky Network (free, no key for basic queries)
OPENSKY_API_URL  = "https://opensky-network.org/api"
ADSB_LOL_URL     = "https://api.adsb.lol/v2"  # Completely free, no auth

# Wildfires — NASA FIRMS (free government satellite)
NASA_FIRMS_URL   = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
# Free key at: https://firms.modaps.eosdis.nasa.gov/api/

# Earthquakes — USGS (free, no key)
USGS_EQ_URL      = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Satellites — CelesTrak (free TLE data, no key)
CELESTRAK_URL    = "https://celestrak.org/SOCRATES/"

# Weather — NOAA CDO, NWS, Open-Meteo, NASA POWER (all free)
NOAA_CLIMATE_URL   = "https://www.ncei.noaa.gov/cdo-web/api/v2"
NWS_ALERTS_URL     = "https://api.weather.gov/alerts/active"          # No key needed
OPEN_METEO_URL     = "https://api.open-meteo.com/v1/forecast"         # No key needed (16-day global)
NASA_POWER_URL     = "https://power.larc.nasa.gov/api/temporal/daily/point"  # No key needed (agroclimatology)

# Energy & Agricultural Commodities (Official US Gov — free email key)
EIA_V2_URL         = "https://api.eia.gov/v2"                         # https://www.eia.gov/opendata/register.php
USDA_NASS_URL      = "https://quickstats.nass.usda.gov/api/api_GET/"  # https://quickstats.nass.usda.gov/api

# Crypto Perpetual Derivatives (Free, no key needed for public market data)
HYPERLIQUID_INFO   = "https://api.hyperliquid.xyz/info"
BINANCE_FAPI_URL   = "https://fapi.binance.com/fapi/v1"

# Multi-Source Equity / FX Cross-Verification (Free tiers)
TIINGO_BASE_URL    = "https://api.tiingo.com"
TWELVEDATA_URL     = "https://api.twelvedata.com"
FMP_BASE_URL       = "https://financialmodelingprep.com/stable"
MASSIVE_BASE_URL   = "https://api.massive.com"
ALPHAVANTAGE_URL   = "https://www.alphavantage.co/query"

# ─────────────────────────────────────────────────────────────
# CORPORATE INTELLIGENCE (All Direct from SEC — Free & Identical to Bloomberg)
# ─────────────────────────────────────────────────────────────

# Insider trading — SEC Form 4 (real-time, free)
SEC_FORM4_RSS    = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=40&search_text=&output=atom"

# Institutional whale portfolios — SEC Form 13F (quarterly)
SEC_13F_SEARCH   = "https://efts.sec.gov/LATEST/search-index?q=%2213F%22&dateRange=custom&startdt={start}&enddt={end}&forms=13F-HR"

# Congressional stock trades — STOCK Act (legally required, public)
HOUSE_DISCLOSURES_URL   = "https://disclosures-clerk.house.gov/PublicDisclosure/FinancialDisclosure"
SENATE_DISCLOSURES_URL  = "https://efts.sec.gov/LATEST/search-index?q=%22periodic+transaction%22&forms=PT"

# M&A deals — SEC Form 8-K, 13D/G, Schedule TO
SEC_MA_RSS       = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+TO&dateb=&owner=include&count=40&output=atom"

# Short interest — FINRA (bi-weekly, free)
FINRA_SHORT_URL  = "https://www.finra.org/investors/learn-to-invest/advanced-investing/short-selling/reg-sho-threshold-securities-list"

# Patent filings — USPTO Open Data (free)
USPTO_API_URL    = "https://developer.uspto.gov/ds-api/oa_citations/v1/records"

# ─────────────────────────────────────────────────────────────
# AI AGENTS (Quota-Proof Multi-Provider Router)
# Source 1: Google Gemini Flash + Gemma 4 (separate per-model free buckets)
# Source 2: Groq LPU Inference (free tier: 30 RPM / 1,000+ RPD per model)
# Source 3: Ollama local models (DeepSeek R1, Qwen 2.5) — zero API cost
# ─────────────────────────────────────────────────────────────
GEMINI_MODEL         = "gemini-3.5-flash"
GEMINI_LITE_MODEL    = "gemini-2.5-flash-lite"
GEMINI_OPEN_MODEL    = "gemma-4-31b-it"
# Free key at: https://aistudio.google.com/apikey

GROQ_BASE_URL        = "https://api.groq.com/openai/v1"
GROQ_MODEL           = "qwen/qwen3.8-27b"
GROQ_REASONING_MODEL = "openai/gpt-oss-120b"
# Free key at: https://console.groq.com/login

OLLAMA_LOCAL_URL = "http://localhost:11434"  # Runs on your own machine
OLLAMA_MODELS    = ["deepseek-r1:7b", "llama3.3:70b", "qwen2.5-finance"]
# Install: https://ollama.ai (completely free, runs offline)

# ─────────────────────────────────────────────────────────────
# PAPER TRADING & ORDER EXECUTION
# Source: Alpaca Markets (free paper + live trading API)
# No monthly fee. No per-trade commissions on US stocks.
# ─────────────────────────────────────────────────────────────
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL  = "https://api.alpaca.markets"
# Free account: https://alpaca.markets

# ─────────────────────────────────────────────────────────────
# HISTORICAL DATA & BACKTESTING
# Source: yfinance (50+ years of daily OHLCV, no key)
# Backtest engine: vectorbt (open-source Python, no cost)
# ─────────────────────────────────────────────────────────────
BACKTEST_ENGINE  = "vectorbt"  # pip install vectorbt

# ─────────────────────────────────────────────────────────────
# LOCAL STORAGE (All embedded, no cloud bills)
# ─────────────────────────────────────────────────────────────
DUCKDB_PATH      = "./data/doomsblerg.duckdb"   # Analytics + historical data
SQLITE_PATH      = "./data/portfolio.db"         # Portfolio, watchlists, settings
CHROMADB_PATH    = "./data/vectorstore"          # SEC filing embeddings for RAG
REDIS_PORT       = 6379                          # Local real-time cache
