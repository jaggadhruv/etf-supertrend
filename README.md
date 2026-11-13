# ETF Supertrend Scanner

Sister tool to the stock Supertrend scanner, for a fixed list of US and Indian ETFs.
Daily Supertrend (ATR 10, multiplier 2.5) flips, filtered by the overall trend, ranked by a
Quality Index, with a per-ETF backtest of "enter on flip, exit at stop or 2R".

## Run

```bash
pip install -r requirements.txt
python scan.py                # both markets, scan + backtest
python scan.py --market US    # or IN
python scan.py --no-backtest  # faster; the backtest-edge part of the score is neutral
```

Output: `reports/etf_supertrend_YYYY-MM-DD.html` (latest 30 kept), a copy at `index.html` for
GitHub Pages, and `reports/backtest_trades_latest.csv` with every backtest trade (handy for Power BI).

GitHub Actions runs it Mon-Fri at 22:30 UTC and commits the report. No secrets needed.
No positions are stored anywhere in the repo.

## Universe

Edit `universe/us_etfs.csv` and `universe/india_etfs.csv`. `signal_eligible = 0` keeps an ETF on the
trend board but out of signals and backtests (LIQUIDCASE ships that way: its price only accrues
overnight interest, so Supertrend flips on it are noise).

## Rules

| Step | Rule |
|---|---|
| Overall trend | **Up**: close above the 200-day SMA *and* the SMA higher than 20 sessions ago. **Down**: the mirror. Anything else is **Neutral** and blocks all flips. Set `REGIME_MODE = "sma"` for plain price-vs-SMA. |
| Long | Supertrend flips up while the trend is Up |
| Short | Supertrend flips down while the trend is Down (US only; India shows these as exit/avoid) |
| Entry | Next session's open (`ENTRY_MODE = "signal_close"` to enter at the flip close) |
| Stop | Supertrend line on the flip bar (fixed, not trailed) |
| Target | 2R from entry |
| Exit | Stop or target, whichever comes first. Gaps fill at the open. If both are touched in one bar, the stop is assumed. |

Why the slope check: a plain 200 SMA cross flips back and forth when price chops around the
average. Requiring the average itself to slope the same way removes most of those whipsaws.
The backtest runs every ETF with and without the filter, so you can see whether it helps.

## Quality Index (0-100)

| Part | Points | Full marks when |
|---|---|---|
| Volume | 20 | Flip-day volume at 2x the 20-day average (0.8x or less scores 0) |
| Trend | 20 | 200 SMA rising 2%+ over 20 sessions, and price 1 to 6 ATR from it (further out is stretched) |
| ADX | 15 | ADX 35+, with +DI/-DI pointing the same way as the flip (halved otherwise) |
| Momentum | 15 | RSI 55-70 for longs (30-45 for shorts); overbought/oversold loses points |
| Weekly | 10 | Weekly Supertrend agrees with the flip |
| Risk | 10 | Stop 2.5 ATR or less from entry (5+ ATR scores 0); a tighter stop reaches 2R sooner |
| Backtest edge | 10 | This ETF's backtested expectancy for that side is +0.5R or better (neutral if fewer than 8 trades) |

Minus 4 points per session since the flip. Grades: A 75+, B 60-74, C 45-59, D below 45.
ETF volume matters less than stock volume (market makers create and redeem units), so treat the
volume score as a participation hint, not a gate. Weights live in `config.py`.

## Backtest metrics

- **Win rate**: share of closed trades that hit 2R. Break-even at a 2R target is 33.3%.
- **Expectancy**: average result per trade in R. The single best measure of edge; above 0 is good.
- **Profit factor**: gross wins / gross losses. Above 1.3 is decent, above 1.6 is strong.
- **Total R / Max DD**: cumulative R and the worst peak-to-trough drop of that R curve.
- **Loss streak**: longest run of consecutive losers (size so you can sit through it).
- **Avg hold / In market**: days per trade and share of time a position was open.
- **System CAGR vs Buy & hold CAGR**: system compounds 1% account risk per trade. On strongly rising
  ETFs, buy & hold usually wins on return; the system's case is lower time in market and smaller drawdowns.
- **No-filter exp.**: expectancy of the same rules without the trend filter.
- A "small sample" flag appears below 20 trades. Don't trust those numbers yet.

Prices are dividend-adjusted (so SCHD/BND results include dividends). No commissions or slippage.

## Swapping in your own Supertrend

`indicators.supertrend()` follows the TradingView method with Wilder ATR. If your stock tool's
`supertrend.py` computes it differently, replace that one function; it must return the columns
`atr`, `st`, `st_dir` (+1/-1) and `st_flip` (+1/-1/0).
