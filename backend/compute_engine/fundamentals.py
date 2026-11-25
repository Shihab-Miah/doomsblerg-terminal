"""
DoomsBlerg Fundamental Valuation & Accounting Quality Engine
============================================================
100% deterministic Python math — zero LLM arithmetic.
Computes WACC, DCF Intrinsic Fair Value, Altman Z-Score, and Piotroski F-Score.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from backend.data_engine.equities import (
    get_company_overview,
    get_financial_statements,
    get_quote_cross_verified,
)
from backend.data_engine.macro_bonds import get_yield_curve


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_wacc(
    market_cap: float,
    total_debt: float,
    beta: float = 1.0,
    risk_free_rate: float = 0.045,
    equity_risk_premium: float = 0.05,
    interest_expense: Optional[float] = None,
    tax_rate: float = 0.21,
) -> Dict[str, Any]:
    """Compute Weighted Average Cost of Capital (WACC) using CAPM."""
    market_cap = max(market_cap, 1.0)
    total_debt = max(total_debt, 0.0)
    beta_clamped = max(0.3, min(beta if beta > 0 else 1.0, 3.0))

    cost_of_equity = risk_free_rate + beta_clamped * equity_risk_premium

    if total_debt > 0 and interest_expense is not None and interest_expense > 0:
        pre_tax_cost_of_debt = max(0.02, min(abs(interest_expense) / total_debt, 0.15))
    else:
        pre_tax_cost_of_debt = risk_free_rate + 0.015

    after_tax_cost_of_debt = pre_tax_cost_of_debt * (1.0 - tax_rate)
    total_capital = market_cap + total_debt
    equity_weight = market_cap / total_capital
    debt_weight = total_debt / total_capital

    wacc = equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt
    return {
        "wacc": round(wacc, 4),
        "wacc_pct": round(wacc * 100, 2),
        "cost_of_equity_pct": round(cost_of_equity * 100, 2),
        "after_tax_cost_of_debt_pct": round(after_tax_cost_of_debt * 100, 2),
        "equity_weight_pct": round(equity_weight * 100, 2),
        "debt_weight_pct": round(debt_weight * 100, 2),
        "risk_free_rate_pct": round(risk_free_rate * 100, 2),
        "beta_used": round(beta_clamped, 3),
    }


def compute_dcf(
    free_cash_flows: List[float],
    shares_outstanding: float,
    total_cash: float,
    total_debt: float,
    current_price: float,
    wacc: float = 0.09,
    growth_rate: Optional[float] = None,
    terminal_growth: float = 0.025,
    projection_years: int = 5,
) -> Dict[str, Any]:
    """
    Discounted Cash Flow (DCF) intrinsic fair value model.
    `free_cash_flows` should be ordered newest-first (e.g., [FY26, FY25, FY24]).
    """
    if not free_cash_flows or shares_outstanding <= 0:
        return {"error": "Insufficient cash flow or share count data for DCF."}

    base_fcf = free_cash_flows[0]
    if base_fcf <= 0:
        # Use average positive FCF if most recent year had a one-off dip
        positives = [x for x in free_cash_flows if x > 0]
        if not positives:
            return {
                "fair_value_per_share": None,
                "valuation_status": "negative_cash_flow",
                "note": "Company has negative free cash flow across recent periods; DCF not applicable.",
            }
        base_fcf = sum(positives) / len(positives)

    if growth_rate is None:
        if len(free_cash_flows) >= 2 and free_cash_flows[-1] > 0 and free_cash_flows[0] > 0:
            n = len(free_cash_flows) - 1
            raw_cagr = (free_cash_flows[0] / free_cash_flows[-1]) ** (1.0 / n) - 1.0
            growth_rate = max(0.02, min(raw_cagr, 0.18))
        else:
            growth_rate = 0.07

    # Ensure WACC strictly exceeds terminal growth for Gordon Growth stability
    wacc = max(wacc, terminal_growth + 0.015)

    projected: List[float] = []
    pv_cash_flows = 0.0
    fcf = base_fcf
    for yr in range(1, projection_years + 1):
        # Gradually fade growth toward terminal rate by year 5
        fade_weight = (yr - 1) / max(projection_years, 1)
        yr_growth = growth_rate * (1 - 0.35 * fade_weight) + terminal_growth * (0.35 * fade_weight)
        fcf = fcf * (1.0 + yr_growth)
        pv = fcf / ((1.0 + wacc) ** yr)
        projected.append(round(fcf, 2))
        pv_cash_flows += pv

    terminal_value = (projected[-1] * (1.0 + terminal_growth)) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + wacc) ** projection_years)

    enterprise_value = pv_cash_flows + pv_terminal
    equity_value = enterprise_value + max(total_cash, 0.0) - max(total_debt, 0.0)
    fair_value = max(0.0, equity_value / shares_outstanding)

    upside_pct = ((fair_value - current_price) / current_price) * 100.0 if current_price > 0 else 0.0
    if upside_pct >= 15.0:
        status = "undervalued"
    elif upside_pct <= -15.0:
        status = "overvalued"
    else:
        status = "fairly_valued"

    return {
        "fair_value_per_share": round(fair_value, 2),
        "current_price": round(current_price, 2),
        "upside_pct": round(upside_pct, 2),
        "valuation_status": status,
        "base_fcf": round(base_fcf, 2),
        "assumed_growth_pct": round(growth_rate * 100, 2),
        "terminal_growth_pct": round(terminal_growth * 100, 2),
        "discount_rate_wacc_pct": round(wacc * 100, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "pv_terminal_share_pct": round((pv_terminal / enterprise_value) * 100, 1) if enterprise_value > 0 else 0.0,
    }


def compute_altman_z_score(
    balance_sheet: Dict[str, Any],
    income_statement: Dict[str, Any],
    market_cap: float,
) -> Dict[str, Any]:
    """
    Compute Altman Z-Score for corporate distress / bankruptcy probability.
    Z > 2.99: Safe | 1.81 - 2.99: Grey Zone | Z < 1.81: Distress Risk.
    """
    total_assets = _safe_float(balance_sheet.get("totalAssets"))
    total_liab = _safe_float(balance_sheet.get("totalLiabilities"))
    if total_assets <= 0 or total_liab <= 0:
        return {"z_score": None, "zone": "unavailable"}

    ca = _safe_float(balance_sheet.get("totalCurrentAssets"))
    cl = _safe_float(balance_sheet.get("totalCurrentLiabilities"))
    working_capital = ca - cl
    retained_earnings = _safe_float(balance_sheet.get("retainedEarnings"))
    ebit = _safe_float(income_statement.get("operatingIncome"))
    revenue = _safe_float(income_statement.get("revenue"))

    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = max(market_cap, 0.0) / total_liab
    x5 = revenue / total_assets

    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    if z > 2.99:
        zone = "safe_zone"
    elif z >= 1.81:
        zone = "grey_zone"
    else:
        zone = "distress_zone"

    return {
        "z_score": round(z, 3),
        "zone": zone,
        "components": {
            "working_capital_to_assets": round(x1, 3),
            "retained_earnings_to_assets": round(x2, 3),
            "ebit_to_assets": round(x3, 3),
            "market_cap_to_liabilities": round(x4, 3),
            "asset_turnover": round(x5, 3),
        },
    }


def compute_piotroski_f_score(
    income_list: List[Dict[str, Any]],
    balance_list: List[Dict[str, Any]],
    cash_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute the 9-point Piotroski F-Score measuring profitability, leverage,
    liquidity, and operating efficiency (newest statement at index 0).
    """
    if len(income_list) < 2 or len(balance_list) < 2 or len(cash_list) < 1:
        return {"f_score": None, "rating": "unavailable"}

    inc0, inc1 = income_list[0], income_list[1]
    bal0, bal1 = balance_list[0], balance_list[1]
    cf0 = cash_list[0]

    ni0 = _safe_float(inc0.get("netIncome"))
    ni1 = _safe_float(inc1.get("netIncome"))
    ocf0 = _safe_float(cf0.get("operatingCashFlow"))
    ta0 = max(_safe_float(bal0.get("totalAssets"), 1.0), 1.0)
    ta1 = max(_safe_float(bal1.get("totalAssets"), 1.0), 1.0)
    rev0 = max(_safe_float(inc0.get("revenue"), 1.0), 1.0)
    rev1 = max(_safe_float(inc1.get("revenue"), 1.0), 1.0)

    roa0 = ni0 / ta0
    roa1 = ni1 / ta1
    lev0 = _safe_float(bal0.get("longTermDebt")) / ta0
    lev1 = _safe_float(bal1.get("longTermDebt")) / ta1
    cr0 = _safe_float(bal0.get("totalCurrentAssets")) / max(_safe_float(bal0.get("totalCurrentLiabilities"), 1.0), 1.0)
    cr1 = _safe_float(bal1.get("totalCurrentAssets")) / max(_safe_float(bal1.get("totalCurrentLiabilities"), 1.0), 1.0)
    sh0 = _safe_float(inc0.get("weightedAverageShsOutDil") or inc0.get("weightedAverageShsOut"))
    sh1 = _safe_float(inc1.get("weightedAverageShsOutDil") or inc1.get("weightedAverageShsOut"))
    gm0 = _safe_float(inc0.get("grossProfit")) / rev0
    gm1 = _safe_float(inc1.get("grossProfit")) / rev1
    at0 = rev0 / ta0
    at1 = rev1 / ta1

    checks = {
        "positive_net_income": ni0 > 0,
        "positive_operating_cash_flow": ocf0 > 0,
        "improving_roa": roa0 > roa1,
        "cash_flow_exceeds_net_income": ocf0 > ni0,
        "decreasing_leverage": lev0 <= lev1,
        "improving_liquidity": cr0 > cr1,
        "no_share_dilution": sh0 <= sh1 if (sh0 > 0 and sh1 > 0) else True,
        "improving_gross_margin": gm0 > gm1,
        "improving_asset_turnover": at0 > at1,
    }
    score = sum(1 for passed in checks.values() if passed)
    rating = "strong_quality" if score >= 7 else ("solid" if score >= 5 else "weak")
    return {"f_score": score, "max_score": 9, "rating": rating, "checks": checks}


def compute_fundamental_snapshot(ticker: str) -> Dict[str, Any]:
    """Run all deterministic fundamental valuations (WACC, DCF, Z-Score, F-Score) for a ticker."""
    ticker = ticker.upper().strip()
    with ThreadPoolExecutor(max_workers=4) as pool:
        q_fut = pool.submit(get_quote_cross_verified, ticker)
        ov_fut = pool.submit(get_company_overview, ticker)
        fin_fut = pool.submit(get_financial_statements, ticker, 4)
        yc_fut = pool.submit(get_yield_curve)

        quote = q_fut.result()
        overview = ov_fut.result()
        fin = fin_fut.result()
        yc = yc_fut.result()

    inc_list = fin.get("income_statement") if isinstance(fin.get("income_statement"), list) else []
    bal_list = fin.get("balance_sheet") if isinstance(fin.get("balance_sheet"), list) else []
    cf_list = fin.get("cash_flow") if isinstance(fin.get("cash_flow"), list) else []

    if not inc_list or not bal_list or not cf_list:
        return {"ticker": ticker, "error": "Missing financial statements from FMP."}

    current_price = _safe_float(quote.get("price"))
    shares = _safe_float(inc_list[0].get("weightedAverageShsOutDil") or inc_list[0].get("weightedAverageShsOut"))
    market_cap = _safe_float(overview.get("market_cap")) or (current_price * shares)
    beta = _safe_float(overview.get("beta"), 1.0)
    rf_10y = _safe_float((yc.get("yields_pct") or {}).get("10 Yr"), 4.5) / 100.0

    bal0 = bal_list[0]
    inc0 = inc_list[0]
    total_debt = _safe_float(bal0.get("totalDebt")) or (
        _safe_float(bal0.get("shortTermDebt")) + _safe_float(bal0.get("longTermDebt"))
    )
    total_cash = _safe_float(bal0.get("cashAndCashEquivalents")) + _safe_float(bal0.get("shortTermInvestments"))
    interest_exp = _safe_float(inc0.get("interestExpense"))

    wacc_res = compute_wacc(
        market_cap=market_cap,
        total_debt=total_debt,
        beta=beta,
        risk_free_rate=rf_10y,
        interest_expense=interest_exp,
    )

    fcfs = [_safe_float(c.get("freeCashFlow")) for c in cf_list]
    dcf_res = compute_dcf(
        free_cash_flows=fcfs,
        shares_outstanding=shares,
        total_cash=total_cash,
        total_debt=total_debt,
        current_price=current_price,
        wacc=wacc_res["wacc"],
    )
    z_res = compute_altman_z_score(bal0, inc0, market_cap)
    f_res = compute_piotroski_f_score(inc_list, bal_list, cf_list)

    return {
        "ticker": ticker,
        "fiscal_period": inc0.get("date"),
        "current_price": current_price,
        "market_cap": round(market_cap, 2),
        "wacc": wacc_res,
        "dcf_valuation": dcf_res,
        "altman_z_score": z_res,
        "piotroski_f_score": f_res,
    }
