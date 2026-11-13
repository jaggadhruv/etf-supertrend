"""Backtest: enter on a Supertrend flip, exit at the flip-bar Supertrend stop or at 2R.

One position per ETF at a time. A new flip is only taken once the previous trade is closed.
"""
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

import config


@dataclass
class Trade:
    ticker: str
    side: str            # "Long" / "Short"
    signal_date: str
    entry_date: str
    entry: float
    stop: float
    target: float
    exit_date: str
    exit_price: float
    exit_reason: str     # target / stop / stop (gap) / target (gap) / stop (same bar) / open
    r: float
    ret_pct: float       # % move on the position, side-adjusted
    bars_held: int
    filtered: bool       # True if the trend filter was applied in this run


def simulate_exit(o, h, l, start, stop, target, side, skip_gap_on_start):
    """Walk forward from bar `start`. Returns (bar_index, exit_price, reason) or None if still open."""
    for j in range(start, len(o)):
        if not (skip_gap_on_start and j == start):
            if (o[j] - stop) * side <= 0:
                return j, o[j], "stop (gap)"
            if (o[j] - target) * side >= 0:
                return j, o[j], "target (gap)"
        adverse = l[j] if side == 1 else h[j]
        favorable = h[j] if side == 1 else l[j]
        hit_stop = (adverse - stop) * side <= 0
        hit_target = (favorable - target) * side >= 0
        if hit_stop and hit_target:
            return j, stop, "stop (same bar)"
        if hit_stop:
            return j, stop, "stop"
        if hit_target:
            return j, target, "target"
    return None


def plan_entry(df: pd.DataFrame, i: int):
    """Entry index, entry price, first bar to check for exits, skip-gap flag."""
    if config.ENTRY_MODE == "signal_close":
        return i, float(df["Close"].iat[i]), i + 1, False
    if i + 1 >= len(df):
        return None
    return i + 1, float(df["Open"].iat[i + 1]), i + 1, True


def warmup_index(df: pd.DataFrame) -> int:
    ok = df["sma"].notna() & df["st"].notna()
    return int(np.argmax(ok.to_numpy())) + 1 if ok.any() else len(df)


def run_backtest(df: pd.DataFrame, ticker: str, allow_shorts: bool, use_filter: bool):
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
    flip = df["st_flip"].to_numpy()
    regime = df["regime"].to_numpy()
    st = df["st"].to_numpy(dtype=float)
    dates = df.index
    start = warmup_index(df)
    trades, skipped, below_min = [], 0, 0
    next_free = start

    for i in range(start, len(df)):
        if i < next_free or flip[i] == 0:
            continue
        side = int(flip[i])
        if side == -1 and not allow_shorts:
            continue
        if use_filter and regime[i] != side:
            continue
        plan = plan_entry(df, i)
        if plan is None:
            break
        ei, entry, check_from, skip_gap = plan
        stop = st[i]
        risk = (entry - stop) * side
        if not risk > 0:
            skipped += 1  # opened beyond the stop
            continue
        if config.TARGET_R * risk / entry * 100 < config.MIN_TARGET_PCT:
            below_min += 1  # move too small to be worth a swing trade
            continue
        target = entry + side * config.TARGET_R * risk
        res = simulate_exit(o, h, l, check_from, stop, target, side, skip_gap)
        if res is None:
            trades.append(Trade(ticker, "Long" if side == 1 else "Short", d(dates[i]), d(dates[ei]),
                                entry, stop, target, "", c[-1], "open", (c[-1] - entry) * side / risk,
                                (c[-1] - entry) * side / entry * 100,
                                len(df) - 1 - ei, use_filter))
            break
        j, px, reason = res
        trades.append(Trade(ticker, "Long" if side == 1 else "Short", d(dates[i]), d(dates[ei]),
                            entry, stop, target, d(dates[j]), px, reason, (px - entry) * side / risk,
                            (px - entry) * side / entry * 100,
                            j - ei, use_filter))
        next_free = j  # a flip on the exit bar can start the next trade

    return trades, metrics(trades, df, start, skipped, below_min)


def d(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _side_stats(rs):
    if len(rs) == 0:
        return {"n": 0, "win_rate": None, "expectancy": None}
    return {"n": len(rs), "win_rate": float((rs > 0).mean() * 100), "expectancy": float(rs.mean())}


def metrics(trades, df, start, skipped=0, below_min=0) -> dict:
    closed = [t for t in trades if t.exit_reason != "open"]
    open_t = [t for t in trades if t.exit_reason == "open"]
    c = df["Close"].to_numpy(dtype=float)
    out = {"bars_tested": max(len(df) - start, 0), "skipped": skipped, "below_min": below_min,
           "open_trade": asdict(open_t[0]) if open_t else None,
           "start_date": d(df.index[start]) if start < len(df) else None,
           "end_date": d(df.index[-1])}

    years = 0.0
    if start < len(df):
        years = max((df.index[-1] - df.index[start]).days / 365.25, 1e-9)
        bh = c[-1] / c[start] - 1
        out["buy_hold_return"] = bh * 100
        out["buy_hold_cagr"] = ((1 + bh) ** (1 / years) - 1) * 100 if years >= 0.5 else None
    out["years"] = years

    rs = np.array([t.r for t in closed], dtype=float)
    out["trades"] = len(rs)
    if len(rs) == 0:
        out.update({k: None for k in ("win_rate", "avg_win", "avg_loss", "expectancy", "profit_factor",
                                      "total_r", "max_dd_r", "max_loss_streak", "avg_bars", "exposure",
                                      "trades_per_year", "system_cagr", "avg_ret_pct",
                                      "avg_win_pct", "avg_loss_pct")})
        out["long"], out["short"] = _side_stats(rs), _side_stats(rs)
        return out

    wins, losses = rs[rs > 0], rs[rs <= 0]
    cum = np.cumsum(rs)
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    streak = best = 0
    for r in rs:
        streak = streak + 1 if r <= 0 else 0
        best = max(best, streak)
    equity = float(np.prod(1 + rs * config.RISK_PCT_FOR_COMPARISON / 100))
    held = sum(t.bars_held + 1 for t in trades)

    out.update({
        "win_rate": float(len(wins) / len(rs) * 100),
        "avg_win": float(wins.mean()) if len(wins) else None,
        "avg_loss": float(losses.mean()) if len(losses) else None,
        "expectancy": float(rs.mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None,
        "total_r": float(rs.sum()),
        "max_dd_r": float((peak - cum).max()),
        "max_loss_streak": int(best),
        "avg_bars": float(np.mean([t.bars_held for t in closed])),
        "exposure": float(held / out["bars_tested"] * 100) if out["bars_tested"] else None,
        "trades_per_year": float(len(rs) / years) if years else None,
        "system_cagr": float((equity ** (1 / years) - 1) * 100) if years >= 0.5 and equity > 0 else None,
        "avg_ret_pct": float(np.mean([t.ret_pct for t in closed])),
        "avg_win_pct": float(np.mean([t.ret_pct for t in closed if t.r > 0])) if len(wins) else None,
        "avg_loss_pct": float(np.mean([t.ret_pct for t in closed if t.r <= 0])) if len(losses) else None,
        "long": _side_stats(np.array([t.r for t in closed if t.side == "Long"])),
        "short": _side_stats(np.array([t.r for t in closed if t.side == "Short"])),
    })
    return out


def aggregate(all_trades) -> dict:
    """Pooled stats across every ETF in a market."""
    closed = [t for t in all_trades if t.exit_reason != "open"]
    rs = np.array([t.r for t in closed], dtype=float)
    if len(rs) == 0:
        return {"trades": 0}
    wins, losses = rs[rs > 0], rs[rs <= 0]
    return {
        "trades": len(rs),
        "win_rate": float(len(wins) / len(rs) * 100),
        "expectancy": float(rs.mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None,
        "total_r": float(rs.sum()),
        "avg_ret_pct": float(np.mean([t.ret_pct for t in closed])),
    }


BREAKEVEN_WIN_RATE = 100 / (1 + config.TARGET_R)
