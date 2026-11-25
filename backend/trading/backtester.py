"""
DoomsBlerg Deterministic Historical Backtester
==============================================
Zero-dependency, zero-lookahead historical strategy simulator using real OHLCV
bars from Phase 1 (`get_historical_prices`) and Phase 2 risk analytics.
"""

import math
from typing import Any, Dict, List, Optional

from backend.compute_engine.portfolio_risk import compute_portfolio_risk
from backend.compute_engine.technicals import ema_series, rsi, sma
from backend.data_engine.equities import get_historical_prices

SUPPORTED_STRATEGIES = {
    "sma_cross": "Trend-following: Buy when 20-day SMA crosses above 50-day SMA; exit on cross below.",
    "rsi_reversion": "Mean-reversion: Buy when 14-day RSI drops <= 35; exit when RSI >= 68.",
    "macd_trend": "Momentum: Buy when MACD histogram turns positive; exit when histogram turns negative.",
}


def _bar_signal(strategy: str, closes_to_date: List[float]) -> Optional[str]:
    """Compute entry/exit signal using strictly historical closes up to current bar (no lookahead)."""
    n = len(closes_to_date)
    if strategy == "sma_cross":
        if n < 51:
            return None
        s20_now = sma(closes_to_date, 20)
        s50_now = sma(closes_to_date, 50)
        s20_prev = sma(closes_to_date[:-1], 20)
        s50_prev = sma(closes_to_date[:-1], 50)
        if None in (s20_now, s50_now, s20_prev, s50_prev):
            return None
        if s20_prev <= s50_prev and s20_now > s50_now:
            return "enter"
        if s20_prev >= s50_prev and s20_now < s50_now:
            return "exit"
        # Allow entering on established bull alignment once warmup completes
        if n == 51 and s20_now > s50_now:
            return "enter"
        return None

    if strategy == "rsi_reversion":
        if n < 16:
            return None
        val = rsi(closes_to_date, 14)
        if val is None:
            return None
        if val <= 35.0:
            return "enter"
        if val >= 68.0:
            return "exit"
        return None

    if strategy == "macd_trend":
        if n < 36:
            return None
        ef = ema_series(closes_to_date, 12)
        es = ema_series(closes_to_date, 26)
        offset = 26 - 12
        macd_line = [ef[i + offset] - es[i] for i in range(len(es))]
        sig_line = ema_series(macd_line, 9)
        if len(sig_line) < 2:
            return None
        hist_now = macd_line[-1] - sig_line[-1]
        hist_prev = macd_line[-2] - sig_line[-2]
        if hist_prev <= 0 < hist_now:
            return "enter"
        if hist_prev >= 0 > hist_now:
            return "exit"
        return None

    raise ValueError(f"Unknown strategy '{strategy}'. Options: {list(SUPPORTED_STRATEGIES.keys())}")


def run_backtest(
    ticker: str,
    strategy: str = "sma_cross",
    range_str: str = "2y",
    initial_capital: float = 10000.0,
    stop_loss_pct: Optional[float] = 8.0,
    take_profit_pct: Optional[float] = None,
    commission_bps: float = 0.0,
) -> Dict[str, Any]:
    """
    Simulate trading `ticker` over historical daily bars without lookahead bias.
    Returns performance vs Buy & Hold, risk ratios, trade log, and sampled equity curve.
    """
    ticker = ticker.upper().strip()
    strategy = strategy.lower().strip()
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unknown strategy '{strategy}'. Options: {list(SUPPORTED_STRATEGIES.keys())}")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    bars = get_historical_prices(ticker, range_str=range_str, interval="1d")
    if len(bars) < 60:
        raise RuntimeError(f"Need at least 60 daily bars to backtest {ticker} (got {len(bars)}).")

    closes = [float(b["close"]) for b in bars]
    cash = float(initial_capital)
    shares = 0.0
    entry_price = 0.0
    entry_date = ""
    fee_rate = max(0.0, commission_bps) / 10000.0

    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    daily_returns: List[float] = []
    prev_equity = initial_capital

    for idx, bar in enumerate(bars):
        close = closes[idx]
        bar_open = float(bar.get("open") or close)
        low = float(bar.get("low") or close)
        high = float(bar.get("high") or close)
        date = bar["date"]

        # Check intraday risk stops while in position
        exited_this_bar = False
        if shares > 0:
            stop_price = entry_price * (1.0 - stop_loss_pct / 100.0) if stop_loss_pct else None
            tp_price = entry_price * (1.0 + take_profit_pct / 100.0) if take_profit_pct else None

            exit_px: Optional[float] = None
            reason = ""
            if stop_price and low <= stop_price:
                exit_px = min(bar_open, stop_price) if bar_open < stop_price else stop_price
                reason = f"stop_loss ({stop_loss_pct}%)"
            elif tp_price and high >= tp_price:
                exit_px = max(bar_open, tp_price) if bar_open > tp_price else tp_price
                reason = f"take_profit ({take_profit_pct}%)"

            if exit_px is not None:
                proceeds = shares * exit_px * (1.0 - fee_rate)
                pnl = proceeds - (shares * entry_price)
                ret_pct = ((exit_px / entry_price) - 1.0) * 100.0
                cash += proceeds
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_px, 2),
                        "return_pct": round(ret_pct, 2),
                        "pnl": round(pnl, 2),
                        "exit_reason": reason,
                    }
                )
                shares = 0.0
                entry_price = 0.0
                entry_date = ""
                exited_this_bar = True

        # Strategy close-of-day signal
        if not exited_this_bar:
            sig = _bar_signal(strategy, closes[: idx + 1])
            if sig == "enter" and shares == 0.0 and cash > 0:
                fill_px = close
                shares = (cash * (1.0 - fee_rate)) / fill_px
                cash = 0.0
                entry_price = fill_px
                entry_date = date
            elif sig == "exit" and shares > 0.0:
                proceeds = shares * close * (1.0 - fee_rate)
                pnl = proceeds - (shares * entry_price)
                ret_pct = ((close / entry_price) - 1.0) * 100.0
                cash += proceeds
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(close, 2),
                        "return_pct": round(ret_pct, 2),
                        "pnl": round(pnl, 2),
                        "exit_reason": "signal_exit",
                    }
                )
                shares = 0.0
                entry_price = 0.0
                entry_date = ""

        mark_equity = cash + shares * close
        if idx > 0 and prev_equity > 0:
            daily_returns.append((mark_equity / prev_equity) - 1.0)
        prev_equity = mark_equity
        equity_curve.append({"date": date, "equity": round(mark_equity, 2), "close": round(close, 2)})

    # Mark open position separately without mutating closed stats, compute final equity
    final_equity = cash + shares * closes[-1]
    total_return_pct = ((final_equity / initial_capital) - 1.0) * 100.0
    bh_return_pct = ((closes[-1] / closes[0]) - 1.0) * 100.0

    bh_daily = [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]
    risk_stats = compute_portfolio_risk(daily_returns, benchmark_returns=bh_daily)

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.99 if gross_win > 0 else 0.0)
    win_rate = round((len(wins) / len(trades)) * 100.0, 1) if trades else 0.0

    # Downsample equity curve <= 120 points for lightweight UI charts
    step = max(1, math.ceil(len(equity_curve) / 120))
    sampled_curve = equity_curve[::step]
    if sampled_curve[-1]["date"] != equity_curve[-1]["date"]:
        sampled_curve.append(equity_curve[-1])

    outperformed = total_return_pct > bh_return_pct
    plain_summary = (
        f"Testing {strategy} on {ticker} over {bars[0]['date']} to {bars[-1]['date']} turned "
        f"${initial_capital:,.0f} into ${final_equity:,.2f} ({total_return_pct:+.2f}%), "
        f"{'beating' if outperformed else 'trailing'} Buy & Hold ({bh_return_pct:+.2f}%) "
        f"with {win_rate}% winning trades and {risk_stats.get('max_drawdown_pct', 0.0)}% max drawdown."
    )

    return {
        "ticker": ticker,
        "strategy": strategy,
        "strategy_description": SUPPORTED_STRATEGIES[strategy],
        "period": f"{bars[0]['date']} to {bars[-1]['date']}",
        "bars_tested": len(bars),
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "buy_and_hold_return_pct": round(bh_return_pct, 2),
        "alpha_vs_buy_hold_pct": round(total_return_pct - bh_return_pct, 2),
        "closed_trades": len(trades),
        "open_position": shares > 0,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": risk_stats.get("sharpe_ratio"),
        "max_drawdown_pct": risk_stats.get("max_drawdown_pct"),
        "plain_english_summary": plain_summary,
        "recent_trades": trades[-10:],
        "equity_curve": sampled_curve,
    }
