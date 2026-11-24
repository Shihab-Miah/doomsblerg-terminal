# 🗣️ DoomsBlerg Plain English Command Dictionary
### Zero Cryptic Abbreviations. Built for Real People.

> [!NOTE]
> The original Bloomberg Terminal uses 1980s 3-letter codes like `DES`, `FA`, `OMON`, and `YCRV`.
> **DoomsBlerg replaces every single one with plain English words, natural questions, and simple commands.**

---

## 1. Equities & Stocks (Company Intelligence)

| Old Bloomberg Code | Plain English Command | What to Type (Natural Slang / Everyday Words) | What You Get |
| :--- | :--- | :--- | :--- |
| `DES` (Description) | **Company Overview** | `about AAPL`, `who is TSMA`, `overview NVDA` | Full profile: what they do, CEO, market cap, sector, products. |
| `FA` (Financial Analysis) | **Financials** | `financials AAPL`, `income statement TSLA`, `balance sheet MSFT` | Full clean accounting: revenue, profit margins, cash flow, debts. |
| `GP` (Graph Price) | **Price Chart** | `chart AAPL`, `show price TSLA`, `candles NVDA` | Interactive candlestick chart with volume and trendlines. |
| `EE` (Earnings Estimates) | **Earnings Forecast** | `earnings forecast AAPL`, `wall street expectations TSLA` | Consensus revenue and EPS forecasts: what Wall Street expects. |
| `ERN` (Earnings Summary) | **Earnings Beat/Miss** | `earnings history AAPL`, `did they beat TSLA` | Historic earnings report results vs expectations. |
| `INSDR` (Insider Trading) | **Insider Activity** | `who is buying AAPL`, `insider trades TSLA` | Real-time SEC Form 4 filings: executives buying or dumping their own stock. |
| `CF` (Company Filings) | **Annual & Quarterly Reports** | `annual report AAPL`, `10k TSLA`, `filings NVDA` | Direct access to official SEC filings (10-K, 10-Q, 8-K). |
| `RV` (Relative Valuation) | **Compare With Rivals** | `compare AAPL to MSFT`, `rivals TSLA`, `peers NVDA` | Valuation multiples (P/E, EV/EBITDA) vs top competitors. |
| `SRCH` (Equity Screener) | **Stock Screener** | `find stocks with P/E under 15`, `screen high dividend` | Search across thousands of companies using simple filters. |
| `SI` (Short Interest) | **Short Squeeze Watch** | `short interest TSLA`, `who is betting against AAPL` | Percentage of shares borrowed by short sellers betting on a drop. |

---

## 2. Valuation & Cold Math (No AI Guesswork)

| Old Bloomberg Code | Plain English Command | What to Type | What You Get |
| :--- | :--- | :--- | :--- |
| `DCF` | **Fair Value Calculator** | `dcf valuation AAPL`, `fair value TSLA`, `what is it worth` | Discounted Cash Flow model computed by Python (real math, no AI). |
| `WACC` | **Cost of Capital** | `cost of capital AAPL`, `wacc MSFT` | Exact Weighted Average Cost of Capital calculation. |
| `BETA` | **Stock Volatility / Beta** | `how volatile is TSLA`, `beta AAPL` | How violently the stock swings compared to the broader S&P 500. |

---

## 3. Options & Derivatives

| Old Bloomberg Code | Plain English Command | What to Type | What You Get |
| :--- | :--- | :--- | :--- |
| `OMON` (Options Monitor) | **Options Chain** | `options AAPL`, `calls and puts TSLA` | Full options table: strike prices, expiration dates, volume. |
| `OVME` (Options Valuation) | **Options Greeks** | `greeks AAPL 250 call`, `implied volatility TSLA` | Black-Scholes pricing, Delta, Gamma, Theta, Vega, IV surface. |

---

## 4. Macroeconomics & Government Data

| Old Bloomberg Code | Plain English Command | What to Type | What You Get |
| :--- | :--- | :--- | :--- |
| `ECO` (Economic Calendar) | **Economic Calendar** | `what economic reports drop this week`, `calendar` | Upcoming CPI, Jobs report (NFP), Fed meetings, GDP releases. |
| `ECST` (Economic Stats) | **Inflation & Jobs Stats** | `show inflation`, `cpi chart`, `unemployment rate` | Direct data feeds from Federal Reserve (FRED) with historical charts. |
| `BTMM` (Treasury & Money) | **Interest Rates Dashboard** | `fed interest rates`, `sofr rate`, `tbill rates` | Fed Funds rate, SOFR, 3-month and 1-year Treasury bill rates. |
| `YCRV` (Yield Curve) | **Yield Curve** | `yield curve`, `is curve inverted` | The US Treasury yield curve: 3M, 2Y, 5Y, 10Y, 30Y benchmark rates. |

---

## 5. Currencies & Commodities

| Old Bloomberg Code | Plain English Command | What to Type | What You Get |
| :--- | :--- | :--- | :--- |
| `FXC` (FX Matrix) | **Currency Rates** | `forex rates`, `usd to eur`, `currency matrix` | Live currency exchange rates and dollar strength index (DXY). |
| `COMS` (Commodities) | **Commodity Prices** | `oil price`, `gold price`, `wheat price`, `commodities` | Crude oil (WTI/Brent), natural gas, gold, copper, corn, soybeans. |

---

## 6. News & Market Mood

| Old Bloomberg Code | Plain English Command | What to Type | What You Get |
| :--- | :--- | :--- | :--- |
| `TOP` / `N` | **Top Headlines** | `news`, `market headlines`, `news about NVDA` | Real-time curated news from financial feeds. |
| *New* | **Market Mood / Sentiment** | `market mood`, `sentiment on TSLA`, `fear and greed` | AI NLP score measuring whether headlines and social chatter are bullish or bearish. |

---

## 7. 🤖 DoomsBlerg Special: AI Agent Council Commands
*(Features Bloomberg does NOT have)*

| Command Name | What to Type | What It Does |
| :--- | :--- | :--- |
| **Debate This Stock** | `debate AAPL`, `bull vs bear TSLA` | Two specialized AI agents face off: Bull Agent pitches the long case, Bear Agent pitches the short case, Risk Officer judge declares a verdict. |
| **Deep Read the 10-K** | `audit filing AAPL`, `read 10k TSLA for red flags` | AI reads all 100+ pages of the annual SEC filing, analyzes footnotes, and highlights hidden liabilities or accounting gimmicks. |
| **Morning Briefing** | `morning briefing`, `what should I watch today` | Multi-agent summary of overnight global markets, top earnings, economic releases, and physical world signals. |
| **Risk Check** | `check portfolio risk`, `stress test my holdings` | Simulates rate hikes, market crashes, or oil spikes on your open positions. |

---

## 8. 🌍 DoomsBlerg Special: God's Eye View (Geospatial Intelligence)
*(Alternative physical-world data that Bloomberg doesn't give retail users)*

| Command Name | What to Type | What It Does & Trading Signal |
| :--- | :--- | :--- |
| **Watch the Globe** | `open globe`, `gods eye view`, `show world map` | Launches full 3D interactive globe with live telemetry overlays. |
| **Track Ships** | `track oil tankers`, `ships near Hormuz`, `port traffic LA` | Live AIS ship tracking via AISStream. Shows congestion, tanker queues, floating storage. |
| **Flight Radar** | `flights near New York`, `track corporate jets` | Live ADS-B flight telemetry via OpenSky. Scans for corporate M&A travel patterns. |
| **Wildfire Watch** | `what is on fire`, `fires near oil fields`, `farm fires` | Live NASA FIRMS satellite data. Flags fires near oil pipelines, refineries, or crop belts. |
| **Earthquake Watch** | `earthquake alerts`, `recent quakes near Taiwan` | Live USGS seismic data. Flags disruptions to semiconductor fabs, ports, or mines. |
| **Supply Chokepoints** | `chokepoints`, `suez traffic`, `panama canal queue` | Live maritime monitor for the 6 critical global trade canals. |
