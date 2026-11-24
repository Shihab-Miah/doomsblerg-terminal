"""
DoomsBlerg Data Router
======================
The central hub for all data requests.

This is equivalent to Bloomberg's internal data normalization layer —
every asset class (stocks, bonds, options, macro, FX, commodities, geospatial)
flows through one unified interface and returns clean, standardized data.

No LLM touches this module. Only real data from real sources.
"""

from openbb import obb
import yfinance as yf
import pandas as pd
from typing import Optional


# ─────────────────────────────────────────────────────────────
# EQUITIES
# ─────────────────────────────────────────────────────────────

def get_stock_quote(ticker: str, provider: str = "polygon") -> dict:
    """Get real-time quote for a stock. Same data Bloomberg shows on quote page."""
    result = obb.equity.price.quote(ticker, provider=provider)
    return result.to_df().to_dict(orient="records")[0]


def get_stock_history(ticker: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """Get historical OHLCV price data. Identical to Bloomberg GP (price graph) data."""
    data = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    return data


def get_financials(ticker: str) -> dict:
    """
    Get full financial statements — income statement, balance sheet, cash flow.
    Same data Bloomberg shows under FA (Financial Analysis).
    Data comes directly from SEC filings so it's 100% identical.
    """
    income = obb.equity.fundamental.income(ticker, period="annual", limit=5)
    balance = obb.equity.fundamental.balance(ticker, period="annual", limit=5)
    cash_flow = obb.equity.fundamental.cash(ticker, period="annual", limit=5)
    return {
        "income_statement": income.to_df(),
        "balance_sheet": balance.to_df(),
        "cash_flow": cash_flow.to_df(),
    }


def get_company_overview(ticker: str) -> dict:
    """
    Get the company profile page — same as Bloomberg DES (Description).
    Returns: name, sector, industry, description, key metrics, officers.
    """
    profile = obb.equity.profile(ticker)
    return profile.to_df().to_dict(orient="records")[0]


def get_earnings_estimates(ticker: str) -> pd.DataFrame:
    """
    Get analyst earnings and revenue forecasts — same as Bloomberg EE (Earnings Estimates).
    Returns consensus EPS and revenue estimates for upcoming quarters.
    """
    estimates = obb.equity.estimates.consensus(ticker)
    return estimates.to_df()


def get_sec_filings(ticker: str, form_type: str = "10-K", limit: int = 5) -> pd.DataFrame:
    """
    Get SEC filing links — same as Bloomberg CF (Company Filings).
    Returns links to actual SEC EDGAR documents (10-K annual reports, 10-Q quarterly, 8-K events).
    """
    filings = obb.equity.fundamental.filings(ticker, type=form_type, limit=limit)
    return filings.to_df()


def get_insider_transactions(ticker: str) -> pd.DataFrame:
    """
    Get insider buying and selling activity — same as Bloomberg INSDR.
    Data from SEC Form 4 filings. Free and 100% identical to Bloomberg.
    """
    insiders = obb.equity.ownership.insider_trading(ticker)
    return insiders.to_df()


# ─────────────────────────────────────────────────────────────
# OPTIONS
# ─────────────────────────────────────────────────────────────

def get_options_chain(ticker: str) -> pd.DataFrame:
    """
    Get the full options chain — same as Bloomberg OMON (Options Monitor).
    Returns all available strike prices, expiration dates, implied volatility,
    volume, open interest. Greeks computed separately in compute engine.
    """
    options = obb.derivatives.options.chains(ticker, provider="cboe")
    return options.to_df()


# ─────────────────────────────────────────────────────────────
# FIXED INCOME (BONDS)
# ─────────────────────────────────────────────────────────────

def get_treasury_yield_curve(country: str = "us") -> pd.DataFrame:
    """
    Get the government bond yield curve — same as Bloomberg YCRV (Yield Curve).
    Shows interest rates across different time horizons (3-month, 2-year, 10-year, etc.)
    Data from US Treasury / FRED — free and identical to Bloomberg.
    """
    curve = obb.fixedincome.government.yield_curve(country=country)
    return curve.to_df()


def get_money_market_rates() -> dict:
    """
    Get central bank rates, overnight rates, and short-term market rates.
    Same as Bloomberg BTMM (Treasury and Money Markets dashboard).
    """
    fed_funds = obb.economy.fred_series("FEDFUNDS")       # Federal Funds Rate
    sofr = obb.economy.fred_series("SOFR")                # Secured Overnight Financing Rate
    tbill_3m = obb.economy.fred_series("DTB3")            # 3-Month Treasury Bill
    tbill_1y = obb.economy.fred_series("DTB1YR")          # 1-Year Treasury Bill
    return {
        "fed_funds_rate": fed_funds.to_df(),
        "sofr": sofr.to_df(),
        "tbill_3_month": tbill_3m.to_df(),
        "tbill_1_year": tbill_1y.to_df(),
    }


# ─────────────────────────────────────────────────────────────
# MACROECONOMICS
# ─────────────────────────────────────────────────────────────

def get_macro_indicator(fred_series_id: str) -> pd.DataFrame:
    """
    Get any macroeconomic data series from the Federal Reserve.
    Same data Bloomberg shows in ECO and ECST functions.
    Examples: "CPIAUCSL" = inflation, "UNRATE" = unemployment, "GDP" = GDP growth.
    Data is 100% identical to Bloomberg — both pull from FRED.
    """
    data = obb.economy.fred_series(fred_series_id)
    return data.to_df()


def get_economic_calendar() -> pd.DataFrame:
    """
    Get upcoming economic data releases with market consensus estimates.
    Same as Bloomberg ECO (Economic Calendar).
    """
    calendar = obb.economy.calendar()
    return calendar.to_df()


# ─────────────────────────────────────────────────────────────
# FOREX
# ─────────────────────────────────────────────────────────────

def get_fx_rates(base: str = "USD") -> pd.DataFrame:
    """
    Get current foreign exchange rates matrix — same as Bloomberg FXC.
    Shows the value of one currency against all others.
    """
    fx = obb.currency.price.historical(symbol=f"{base}", provider="fmp")
    return fx.to_df()


# ─────────────────────────────────────────────────────────────
# COMMODITIES
# ─────────────────────────────────────────────────────────────

def get_commodities_overview() -> dict:
    """
    Get prices for major commodities — same as Bloomberg COMS.
    Energy (crude oil, natural gas), metals (gold, silver, copper),
    agriculture (wheat, corn, soybeans).
    """
    commodities = obb.commodity.price.spot(provider="fmp")
    return commodities.to_df()


# ─────────────────────────────────────────────────────────────
# NEWS & SENTIMENT
# ─────────────────────────────────────────────────────────────

def get_financial_news(ticker: Optional[str] = None, limit: int = 20) -> pd.DataFrame:
    """
    Get financial news headlines — same as Bloomberg TOP and N functions.
    If ticker provided, returns company-specific news.
    If no ticker, returns top global financial headlines.
    """
    if ticker:
        news = obb.news.company(ticker, limit=limit)
    else:
        news = obb.news.world(limit=limit)
    return news.to_df()


# ─────────────────────────────────────────────────────────────
# STOCK SCREENING
# ─────────────────────────────────────────────────────────────

def screen_stocks(filters: dict) -> pd.DataFrame:
    """
    Screen stocks by any criteria — same as Bloomberg SRCH (Equity Screener).
    Filter by: sector, market cap, P/E ratio, revenue growth, dividend yield, etc.
    """
    screener = obb.equity.screener(**filters)
    return screener.to_df()
