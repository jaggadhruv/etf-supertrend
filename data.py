"""Price data: sequential yfinance fetch with a fixed delay (same pattern as the stock tool)."""
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

import config


def load_universe(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    df["ticker"] = df["ticker"].str.strip().str.upper()
    df = df[df["ticker"] != ""].drop_duplicates("ticker")
    df["signal_eligible"] = df["signal_eligible"].isin(["1", "true", "True", "yes"])
    return df.reset_index(drop=True)


def fetch_history(ticker: str, years: int = config.HISTORY_YEARS) -> pd.DataFrame | None:
    """Daily OHLCV, dividend/split adjusted. Returns None if no usable data."""
    import yfinance as yf

    start = (datetime.now(timezone.utc) - timedelta(days=int(years * 365.25))).strftime("%Y-%m-%d")
    last_err = None
    for attempt in range(config.FETCH_RETRIES):
        try:
            df = yf.Ticker(ticker).history(start=start, interval="1d", auto_adjust=True)
            if df is not None and not df.empty:
                return clean(df)
            last_err = "empty response"
        except Exception as exc:  # network, rate limit, delisted
            last_err = str(exc)
        time.sleep(config.FETCH_DELAY_SEC * (attempt + 2))
    print(f"  ! {ticker}: no data ({last_err})")
    return None


def clean(df: pd.DataFrame) -> pd.DataFrame | None:
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["High"] > 0) & (df["Low"] > 0)]
    df["Volume"] = df["Volume"].fillna(0)
    return df if len(df) > 30 else None
