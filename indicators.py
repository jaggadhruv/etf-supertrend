"""Technical indicators. Pure pandas/numpy, no TA library dependency.

supertrend() follows the TradingView ta.supertrend logic with Wilder (RMA) ATR.
If your stock tool's supertrend.py differs, replace this one function: everything
else only relies on the columns it returns (atr, st, st_dir, st_flip).
"""
import numpy as np
import pandas as pd


def rma(series: pd.Series, period: int) -> pd.Series:
    """Wilder's moving average."""
    return series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [df["High"] - df["Low"], (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    return rma(true_range(df), period)


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 2.5) -> pd.DataFrame:
    """Returns atr, st (line), st_dir (+1 up / -1 down), st_flip (+1 buy flip, -1 sell flip, 0)."""
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    a = atr(df, period).to_numpy(dtype=float)
    n = len(df)

    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * a
    basic_lower = hl2 - multiplier * a

    fu = np.full(n, np.nan)
    fl = np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)
    st = np.full(n, np.nan)
    flip = np.zeros(n, dtype=int)

    valid = np.flatnonzero(~np.isnan(a))
    if len(valid):
        s = valid[0]
        fu[s], fl[s] = basic_upper[s], basic_lower[s]
        direction[s] = 1 if close[s] >= hl2[s] else -1
        st[s] = fl[s] if direction[s] == 1 else fu[s]
        for i in range(s + 1, n):
            fu[i] = basic_upper[i] if (basic_upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
            fl[i] = basic_lower[i] if (basic_lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
            if direction[i - 1] == -1:
                direction[i] = 1 if close[i] > fu[i] else -1
            else:
                direction[i] = -1 if close[i] < fl[i] else 1
            st[i] = fl[i] if direction[i] == 1 else fu[i]
            if direction[i] != direction[i - 1]:
                flip[i] = direction[i]

    return pd.DataFrame({"atr": a, "st": st, "st_dir": direction, "st_flip": flip}, index=df.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = rma(delta.clip(lower=0), period)
    loss = rma(-delta.clip(upper=0), period)
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0)


def adx(df: pd.DataFrame, period: int = 14):
    """Returns (adx, +DI, -DI)."""
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr_ = rma(true_range(df), period).replace(0, np.nan)
    plus_di = 100 * rma(plus_dm, period) / atr_
    minus_di = 100 * rma(minus_dm, period) / atr_
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    return rma(dx, period), plus_di, minus_di

