"""Regime filter, flip detection and the flip Quality Index."""
import math

import numpy as np
import pandas as pd

import config
from backtest import plan_entry, simulate_exit
from indicators import adx, rsi, supertrend, to_weekly


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    out = df.join(supertrend(df, config.ATR_PERIOD, config.ATR_MULTIPLIER))
    out["sma"] = out["Close"].rolling(config.SMA_PERIOD).mean()
    out["sma_slope_pct"] = (out["sma"] / out["sma"].shift(config.SMA_SLOPE_LOOKBACK) - 1) * 100
    up = out["Close"] > out["sma"]
    down = out["Close"] < out["sma"]
    if config.REGIME_MODE == "sma_slope":
        up &= out["sma_slope_pct"] > 0
        down &= out["sma_slope_pct"] < 0
    out["regime"] = np.select([up, down], [1, -1], 0)
    out["rsi"] = rsi(out["Close"])
    out["adx"], out["plus_di"], out["minus_di"] = adx(out)
    avg_vol = out["Volume"].shift(1).rolling(20).mean()
    out["vol_ratio"] = (out["Volume"] / avg_vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    return out


def weekly_direction(df: pd.DataFrame) -> int:
    w = to_weekly(df)
    if len(w) < config.ATR_PERIOD + 3:
        return 0
    return int(supertrend(w, config.ATR_PERIOD, config.ATR_MULTIPLIER)["st_dir"].iloc[-1])


REGIME_NAME = {1: "Up", -1: "Down", 0: "Neutral"}


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def quality(row, side: int, risk: float, weekly_dir: int, edge: dict | None, age: int):
    """Quality Index 0-100. Returns (score, parts{name: points}, notes[list])."""
    W = config.QUALITY_WEIGHTS
    parts, notes = {}, []

    vr = row["vol_ratio"]
    if _ok(vr) and vr > 0:
        parts["volume"] = _clip((vr - 0.8) / 1.2) * W["volume"]  # 0.8x -> 0, 2.0x -> full
    else:
        parts["volume"] = 0.5 * W["volume"]
        notes.append("no volume data, volume scored neutral")

    slope = row["sma_slope_pct"] * side if _ok(row["sma_slope_pct"]) else 0.0
    dist = (row["Close"] - row["sma"]) / row["atr"] * side if _ok(row["sma"]) and row["atr"] > 0 else 0.0
    if dist < 1:
        dist_frac = _clip(dist)
    elif dist <= 6:
        dist_frac = 1.0
    else:
        dist_frac = _clip(1 - (dist - 6) / 4)
        notes.append(f"stretched {dist:.1f} ATR from the {config.SMA_PERIOD}-day SMA")
    parts["trend"] = (0.5 * _clip(slope / 2.0) + 0.5 * dist_frac) * W["trend"]

    a = row["adx"] if _ok(row["adx"]) else 0.0
    adx_frac = _clip((a - 15) / 20)
    di_ok = (row["plus_di"] > row["minus_di"]) if side == 1 else (row["minus_di"] > row["plus_di"])
    if not di_ok:
        adx_frac *= 0.5
        notes.append("+DI/-DI not yet aligned with the flip")
    parts["adx"] = adx_frac * W["adx"]

    r = row["rsi"] if side == 1 else 100 - row["rsi"]
    if not _ok(r):
        mom = 0.5
    elif 55 <= r <= 70:
        mom = 1.0
    elif 50 <= r < 55:
        mom = 0.7
    elif 70 < r <= 78:
        mom = 0.55
    elif r > 78:
        mom = 0.2
        notes.append("RSI overextended")
    else:
        mom = _clip(r / 50) * 0.4
    parts["momentum"] = mom * W["momentum"]

    parts["weekly"] = W["weekly"] if weekly_dir == side else 0.0
    if weekly_dir != side:
        notes.append("weekly Supertrend disagrees")

    r_atr = risk / row["atr"] if row["atr"] > 0 else 5
    parts["risk"] = _clip((5 - r_atr) / 2.5) * W["risk"]

    if edge and edge.get("n", 0) >= config.MIN_TRADES_FOR_EDGE_SCORE and edge.get("expectancy") is not None:
        parts["edge"] = _clip((edge["expectancy"] + 0.1) / 0.6) * W["edge"]
    else:
        parts["edge"] = 0.5 * W["edge"]
        notes.append("limited backtest history, edge scored neutral")

    raw = sum(parts.values())
    penalty = age * config.FRESHNESS_PENALTY_PER_BAR
    if age:
        notes.append(f"{age} bar{'s' if age > 1 else ''} old (-{penalty} pts)")
    return max(0.0, raw - penalty), parts, notes


def grade(score: float) -> str:
    for cutoff, g in config.GRADE_BANDS:
        if score >= cutoff:
            return g
    return "D"


def snapshot(df: pd.DataFrame) -> dict:
    """Current state for the trend board."""
    last = df.iloc[-1]
    flips = np.flatnonzero(df["st_flip"].to_numpy() != 0)
    return {
        "close": float(last["Close"]),
        "regime": int(last["regime"]),
        "st_dir": int(last["st_dir"]),
        "st": float(last["st"]) if _ok(last["st"]) else None,
        "bars_since_flip": int(len(df) - 1 - flips[-1]) if len(flips) else None,
        "sma": float(last["sma"]) if _ok(last["sma"]) else None,
        "date": df.index[-1].strftime("%Y-%m-%d"),
    }


def find_signals(df: pd.DataFrame, meta: dict, market: dict, edge_by_side: dict):
    """Latest flip per ETF within the lookback window.

    Returns (signal or None, info or None). `info` holds flips that were blocked by the
    trend filter or are not actionable (bearish flips where shorting is not allowed).
    """
    n = len(df)
    lo = max(n - config.SIGNAL_LOOKBACK_BARS, 1)
    idx = [i for i in range(lo, n) if df["st_flip"].iat[i] != 0]
    if not idx:
        return None, None
    i = idx[-1]
    side = int(df["st_flip"].iat[i])
    row = df.iloc[i]
    age = n - 1 - i
    base = {"ticker": meta["ticker"], "name": meta["name"], "side": "Long" if side == 1 else "Short",
            "flip_date": df.index[i].strftime("%Y-%m-%d"), "age": age,
            "regime": REGIME_NAME[int(row["regime"])]}

    if int(row["regime"]) != side:
        return None, {**base, "kind": "blocked",
                      "reason": f"trend is {REGIME_NAME[int(row['regime'])].lower()}, flip is {base['side'].lower()}"}
    if side == -1 and not market["allow_shorts"]:
        return None, {**base, "kind": "exit",
                      "reason": "bearish flip in a downtrend: exit or avoid longs (no overnight ETF shorts)"}

    plan = plan_entry(df, i)
    if plan is None:  # flip on the latest bar: entry is next open, use close as the reference
        entry, entry_idx, pending = float(row["Close"]), i, True
    else:
        entry_idx, entry, _, _ = plan
        pending = False
    stop = float(row["st"])
    risk = (entry - stop) * side
    if not risk > 0:
        return None, {**base, "kind": "blocked", "reason": "opened beyond the stop"}
    target = entry + side * config.TARGET_R * risk

    status = "Pending entry" if pending else "Active"
    exit_r = None
    if not pending:
        o, h, l = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low"))
        res = simulate_exit(o, h, l, entry_idx, stop, target, side, config.ENTRY_MODE == "next_open")
        if res is not None:
            status = "Target hit" if "target" in res[2] else "Stopped"
            exit_r = (res[1] - entry) * side / risk

    last_close = float(df["Close"].iat[-1])
    score, parts, notes = quality(row, side, risk, weekly_direction(df.iloc[: i + 1]),
                                  edge_by_side.get(base["side"].lower()), age)
    rpt = market.get("risk_per_trade")
    units = rpt / risk if rpt else None
    return {
        **base, "kind": "signal", "status": status, "entry": entry, "entry_pending": pending,
        "stop": stop, "target": target, "risk": risk, "risk_pct": risk / entry * 100,
        "last_close": last_close, "r_now": exit_r if exit_r is not None else (last_close - entry) * side / risk,
        "units": units, "position_value": units * entry if units else None,
        "score": score, "grade": grade(score), "parts": parts, "notes": notes,
        "vol_ratio": float(row["vol_ratio"]) if _ok(row["vol_ratio"]) else None,
        "rsi": float(row["rsi"]) if _ok(row["rsi"]) else None,
        "adx": float(row["adx"]) if _ok(row["adx"]) else None,
    }, None


def rank(signals: list) -> list:
    order = {"Pending entry": 0, "Active": 0, "Target hit": 1, "Stopped": 2}
    return sorted(signals, key=lambda s: (order.get(s["status"], 3), -s["score"]))
