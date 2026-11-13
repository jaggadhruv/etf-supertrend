"""ETF Supertrend Scanner: all tunable settings live here."""

# Supertrend (same as the stock Supertrend tool)
ATR_PERIOD = 10
ATR_MULTIPLIER = 2.5

# Overall trend (regime) filter
#   "sma"        -> Up if Close > SMA, Down if Close < SMA
#   "sma_slope"  -> Up only if Close > SMA AND SMA is rising over SMA_SLOPE_LOOKBACK bars
#                   (mirror for Down). Anything in between is Neutral and blocks all flips.
SMA_PERIOD = 200
SMA_SLOPE_LOOKBACK = 20
REGIME_MODE = "sma_slope"

# Scanner
SIGNAL_LOOKBACK_BARS = 5          # flips within the last N daily bars are shown
FRESHNESS_PENALTY_PER_BAR = 4     # quality points removed per bar since the flip
HISTORY_YEARS = 15                # price history pulled for indicators + backtest
FETCH_DELAY_SEC = 0.3             # sequential fetch delay (avoids Yahoo rate limits)
FETCH_RETRIES = 3

# Trade rules (scanner + backtest use the same rules)
ENTRY_MODE = "next_open"          # "next_open" (realistic) or "signal_close"
TARGET_R = 2.0                    # exit at 2R
# Stop = Supertrend line on the flip bar. Exit = stop or 2R, whichever comes first.
# If stop and target are both touched in the same bar, the stop is assumed (conservative).

# Markets
MARKETS = {
    "US": {
        "label": "United States",
        "file": "universe/us_etfs.csv",
        "currency": "$",
        "allow_shorts": True,
        "risk_per_trade": 50.0,   # used for position size and $ P&L; set None to hide
    },
    "IN": {
        "label": "India",
        "file": "universe/india_etfs.csv",
        "currency": "₹",
        # Retail cannot hold ETF shorts overnight in the Indian cash market, so bearish
        # flips are reported as exit/avoid signals and the backtest is long-only.
        "allow_shorts": False,
        "risk_per_trade": None,
    },
}

# Backtest reporting
MIN_TRADES_FOR_CONFIDENCE = 20    # below this the report flags a small sample
RISK_PCT_FOR_COMPARISON = 1.0     # % of account risked per trade when comparing to buy & hold
MIN_TRADES_FOR_EDGE_SCORE = 8     # backtest needs this many trades to feed the quality score

# Quality index weights (sum to 100)
QUALITY_WEIGHTS = {
    "volume": 20,     # relative volume on the flip bar
    "trend": 20,      # SMA200 slope + healthy distance from SMA200
    "adx": 15,        # trend strength, with DI direction check
    "momentum": 15,   # RSI in the healthy zone, not overextended
    "weekly": 10,     # weekly Supertrend agrees with the flip
    "risk": 10,       # stop distance in ATRs (tighter = easier 2R)
    "edge": 10,       # this ETF's own backtested expectancy for this side
}
GRADE_BANDS = [(75, "A"), (60, "B"), (45, "C"), (0, "D")]

# Output
REPORT_DIR = "reports"
KEEP_REPORTS = 30
